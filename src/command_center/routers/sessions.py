"""Sessions WebSocket + REST API"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from command_center import db
from command_center.services.monitor import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


@router.websocket("/ws/sessions")
async def ws_sessions(ws: WebSocket):
    """실시간 세션 모니터링 WebSocket.

    클라이언트 → 서버: {"type": "get_output", "job_id": "xxx", "from_line": 0}
    서버 → 클라이언트: {"type": "sessions", "data": [...]} (5초 폴링)
    서버 → 클라이언트: {"type": "output", "job_id": "xxx", "lines": [...]}
    """
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "get_output":
                await _send_job_output(ws, msg.get("job_id", ""), msg.get("from_line", 0))

    except WebSocketDisconnect:
        manager.disconnect(ws)


async def _send_job_output(ws: WebSocket, job_id: str, from_line: int) -> None:
    """특정 Job의 stream-json 출력을 from_line부터 전송"""
    job = await db.get_job(job_id)
    if not job or not job.get("output_path"):
        await ws.send_text(json.dumps({
            "type": "output",
            "job_id": job_id,
            "lines": [],
            "total": 0,
        }))
        return

    try:
        with open(job["output_path"], "r", errors="replace") as f:
            all_lines = f.readlines()

        # 각 라인을 파싱하여 구조화
        parsed = []
        for i, line in enumerate(all_lines[from_line:], start=from_line):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                parsed.append({"index": i, **_summarize_event(obj)})
            except json.JSONDecodeError:
                parsed.append({"index": i, "type": "raw", "text": line[:300]})

        await ws.send_text(json.dumps({
            "type": "output",
            "job_id": job_id,
            "lines": parsed[-100:],  # 최근 100개만
            "total": len(all_lines),
        }))
    except FileNotFoundError:
        await ws.send_text(json.dumps({
            "type": "output",
            "job_id": job_id,
            "lines": [],
            "total": 0,
        }))


def _summarize_event(obj: dict) -> dict:
    """stream-json 이벤트를 UI 표시용으로 요약"""
    msg_type = obj.get("type", "unknown")

    if msg_type == "assistant" and "message" in obj:
        content = obj["message"].get("content", [])
        texts = []
        for block in content:
            if block.get("type") == "text":
                texts.append(block["text"][:300])
            elif block.get("type") == "tool_use":
                texts.append(f"[tool: {block.get('name', '?')}]")
        return {"type": "assistant", "text": "\n".join(texts) if texts else "..."}

    if msg_type == "tool_use":
        return {"type": "tool_use", "text": f"[{obj.get('name', '?')}] {obj.get('input', {}).get('command', '')[:100]}"}

    if msg_type == "tool_result":
        content = str(obj.get("content", ""))[:200]
        return {"type": "tool_result", "text": content}

    if msg_type == "result":
        return {"type": "result", "text": (obj.get("result") or "")[:300]}

    return {"type": msg_type, "text": json.dumps(obj)[:200]}


# ── REST endpoints ──


@router.get("/api/sessions")
async def list_sessions():
    """현재 running 중인 세션 목록 (REST)"""
    running = await db.list_jobs(status="running")
    return [
        {
            "job_id": j["id"],
            "title": j["title"],
            "pid": j.get("pid"),
            "started_at": j.get("started_at"),
            "model": j.get("model"),
            "work_dir": j.get("work_dir"),
        }
        for j in running
    ]

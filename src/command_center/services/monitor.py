"""Session monitor - Claude 프로세스 폴링 + WebSocket 브로드캐스트"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket

from command_center import db

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


# ── WebSocket Connection Manager ──


class ConnectionManager:
    """다수의 WebSocket 클라이언트를 관리하고 브로드캐스트한다."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WS 클라이언트 연결 (total=%d)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("WS 클라이언트 해제 (total=%d)", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        """모든 연결에 JSON 메시지 브로드캐스트. 실패한 연결은 제거."""
        dead: list[WebSocket] = []
        message = json.dumps(data)
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ── Process Discovery ──


@dataclass
class SessionInfo:
    pid: int
    job_id: str | None = None
    title: str | None = None
    started_at: str | None = None
    output_lines: int = 0


@dataclass
class MonitorState:
    sessions: dict[int, SessionInfo] = field(default_factory=dict)
    _task: asyncio.Task | None = field(default=None, repr=False)


_state = MonitorState()


async def _discover_claude_pids() -> set[int]:
    """pgrep로 실행 중인 claude --print 프로세스 PID 반환"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep", "-f", "claude.*--print",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if not stdout:
            return set()
        return {int(line) for line in stdout.decode().strip().splitlines() if line.strip().isdigit()}
    except Exception:
        return set()


async def _build_session_snapshot() -> list[dict]:
    """DB running jobs + 프로세스 상태를 결합한 세션 스냅샷"""
    running_jobs = await db.list_jobs(status="running")
    live_pids = await _discover_claude_pids()

    sessions: list[dict] = []
    for job in running_jobs:
        pid = job.get("pid")
        alive = pid is not None and pid in live_pids
        output_lines = 0
        last_output = None

        # output 파일에서 라인 수 + 마지막 줄 추출
        output_path = job.get("output_path")
        if output_path:
            try:
                with open(output_path, "r", errors="replace") as f:
                    lines = f.readlines()
                    output_lines = len(lines)
                    if lines:
                        last_line = lines[-1].strip()
                        try:
                            obj = json.loads(last_line)
                            msg_type = obj.get("type", "")
                            if msg_type == "assistant" and "message" in obj:
                                content = obj["message"].get("content", [])
                                for block in reversed(content):
                                    if block.get("type") == "text":
                                        last_output = block["text"][:200]
                                        break
                            elif msg_type == "tool_use":
                                last_output = f"[tool] {obj.get('name', '?')}"
                        except (json.JSONDecodeError, AttributeError):
                            last_output = last_line[:200]
            except FileNotFoundError:
                pass

        sessions.append({
            "job_id": job["id"],
            "title": job["title"],
            "pid": pid,
            "alive": alive,
            "started_at": job.get("started_at"),
            "output_lines": output_lines,
            "last_output": last_output,
            "model": job.get("model", "sonnet"),
            "work_dir": job.get("work_dir", "~"),
        })

    return sessions


# ── Polling Loop ──


async def _poll_loop() -> None:
    """백그라운드 폴링 루프 — 세션 스냅샷을 WS로 브로드캐스트"""
    while True:
        try:
            if manager.count > 0:
                snapshot = await _build_session_snapshot()
                await manager.broadcast({
                    "type": "sessions",
                    "data": snapshot,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            logger.exception("Monitor poll error")
        await asyncio.sleep(POLL_INTERVAL)


def start_monitor() -> None:
    """lifespan에서 호출 — 폴링 태스크 시작"""
    if _state._task is None or _state._task.done():
        _state._task = asyncio.create_task(_poll_loop())
        logger.info("Monitor 폴링 시작 (interval=%ds)", POLL_INTERVAL)


def stop_monitor() -> None:
    """lifespan 종료 시 호출"""
    if _state._task and not _state._task.done():
        _state._task.cancel()
        logger.info("Monitor 폴링 중지")


# ── Desktop Notification ──


async def notify_job_complete(job_title: str, status: str) -> None:
    """osascript로 macOS 데스크탑 알림 전송"""
    icon = "✅" if status == "completed" else "❌"
    title = f"{icon} Command Center"
    message = f"Job '{job_title}' {status}"
    try:
        await asyncio.create_subprocess_exec(
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"',
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except Exception:
        logger.debug("Desktop notification failed for %s", job_title)

"""Job executor - claude --print subprocess 관리"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from command_center.config import DATA_DIR
from command_center import db
from command_center.services.monitor import manager, notify_job_complete

logger = logging.getLogger(__name__)

OUTPUT_DIR = DATA_DIR / "outputs"

_MODEL_MAP = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


async def run_job(job: dict) -> None:
    """Job을 실행하고 DB 상태를 업데이트한다."""
    job_id = job["id"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / f"{job_id}.jsonl")
    session_id = job.get("session_id") or str(uuid.uuid4())

    await db.update_job(job_id, {
        "status": "running",
        "session_id": session_id,
        "output_path": output_path,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    cmd = _build_cmd(job, session_id)
    timeout_sec = (job.get("timeout_min") or 30) * 60
    proc: asyncio.subprocess.Process | None = None

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_resolve_workdir(job.get("work_dir", "~")),
        )
        await db.update_job(job_id, {"pid": proc.pid})
        logger.info("Job %s 시작 (pid=%d): %s", job_id, proc.pid, job["title"])

        async with asyncio.timeout(timeout_sec):
            stdout_bytes, stderr_bytes = await proc.communicate()

        # stream-json 출력 저장
        if stdout_bytes:
            Path(output_path).write_bytes(stdout_bytes)

        if proc.returncode == 0:
            result_summary = _extract_result_summary(stdout_bytes)
            await db.update_job(job_id, {
                "status": "completed",
                "result_summary": result_summary,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "pid": None,
            })
            logger.info("Job %s 완료", job_id)
            await _broadcast_status(job_id, job["title"], "completed")
            await notify_job_complete(job["title"], "completed")
        else:
            error_msg = (stderr_bytes or b"").decode(errors="replace")[:500]
            await _handle_failure(job, error_msg)

    except TimeoutError:
        error_msg = f"timeout after {job.get('timeout_min', 30)}min"
        await _handle_failure(job, error_msg)
        if proc is not None:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
        logger.warning("Job %s 타임아웃", job_id)

    except Exception as e:
        await _handle_failure(job, str(e))
        logger.exception("Job %s 실행 중 예외", job_id)


def _build_cmd(job: dict, session_id: str) -> list[str]:
    """claude CLI 명령어 구성"""
    model = _MODEL_MAP.get(job.get("model", "sonnet"), "claude-sonnet-4-6")
    effort = job.get("effort", "high")

    cmd = [
        "claude",
        "--print",
        "--output-format", "stream-json",
        "--permission-mode", "dontAsk",
        "--model", model,
        "--session-id", session_id,
        "--max-budget-usd", str(job.get("max_budget", 2.0)),
        "--effort", effort,
        "-p", job["prompt"],
    ]

    if job.get("use_worktree"):
        cmd.append("--worktree")

    return cmd


def _resolve_workdir(work_dir: str) -> str:
    return str(Path(work_dir).expanduser())


def _extract_result_summary(stdout_bytes: bytes) -> str:
    """stream-json에서 마지막 result 메시지 추출"""
    if not stdout_bytes:
        return ""
    for line in reversed(stdout_bytes.decode(errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "result":
                return (obj.get("result") or "")[:500]
        except (json.JSONDecodeError, AttributeError):
            pass
    return ""


async def _handle_failure(job: dict, error_msg: str) -> None:
    """실패 처리 - 재시도 횟수에 따라 queued 또는 failed로 전환"""
    job_id = job["id"]
    retry_count = (job.get("retry_count") or 0) + 1
    max_retries = job.get("max_retries") or 2

    if retry_count <= max_retries:
        await db.update_job(job_id, {
            "status": "queued",
            "retry_count": retry_count,
            "error_message": f"[retry {retry_count}/{max_retries}] {error_msg}",
            "pid": None,
        })
        logger.warning("Job %s 재시도 예약 (%d/%d): %s", job_id, retry_count, max_retries, error_msg)
    else:
        await db.update_job(job_id, {
            "status": "failed",
            "error_message": error_msg,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "pid": None,
        })
        logger.error("Job %s 실패 (재시도 소진): %s", job_id, error_msg)
        await _broadcast_status(job_id, job["title"], "failed")
        await notify_job_complete(job["title"], "failed")


async def _broadcast_status(job_id: str, title: str, status: str) -> None:
    """WS로 Job 상태 변경 이벤트 브로드캐스트"""
    await manager.broadcast({
        "type": "job_status",
        "job_id": job_id,
        "title": title,
        "status": status,
    })

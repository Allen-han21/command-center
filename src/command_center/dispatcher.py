"""launchd entrypoint - FastAPI 의존 없는 standalone 스크립트

실행 방법:
    python -m command_center.dispatcher   # 직접 실행
    launchctl start com.dominium.command-center  # launchd 트리거
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import sys

from command_center.config import DATA_DIR, DISPATCHER_LOG
from command_center.db import init_db, get_job
from command_center.services.scheduler import pick_next_job
from command_center.services.budget_guard import can_spend, record_spend
from command_center.services.executor import run_job

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        DISPATCHER_LOG, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, logging.StreamHandler(sys.stdout)],
    )


async def main() -> None:
    _setup_logging()
    logger.info("─── Dispatcher 시작 ───")

    await init_db()

    job = await pick_next_job()
    if job is None:
        logger.info("실행 가능한 Job 없음 — 종료")
        return

    max_budget = job.get("max_budget", 2.0)
    if not await can_spend(max_budget):
        logger.warning("예산 부족으로 Job %s 스킵 ($%.2f)", job["id"], max_budget)
        return

    logger.info("Job 실행: %s — %s", job["id"], job["title"])
    await run_job(job)

    # 완료 여부 확인 후 지출 기록
    finished = await get_job(job["id"])
    if finished and finished.get("status") == "completed":
        await record_spend(job["id"], max_budget)

    logger.info("─── Dispatcher 완료 ───")


if __name__ == "__main__":
    asyncio.run(main())

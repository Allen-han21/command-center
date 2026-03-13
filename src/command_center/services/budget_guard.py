"""예산 관리 - 일일 한도 체크 + 지출 기록"""

from __future__ import annotations

import logging
from datetime import date

from command_center import db

logger = logging.getLogger(__name__)


async def can_spend(amount: float) -> bool:
    """금일 예산으로 amount를 지출할 수 있는지 확인"""
    budget = await db.get_budget()
    if budget is None:
        logger.warning("예산 레코드 없음 — 지출 거부")
        return False

    remaining = budget.get("remaining_usd", 0.0)
    if remaining < amount:
        logger.warning(
            "예산 부족: 필요 $%.2f, 잔여 $%.2f (한도 $%.2f / 지출 $%.2f)",
            amount,
            remaining,
            budget.get("limit_usd", 0.0),
            budget.get("spent_usd", 0.0),
        )
        return False

    return True


async def record_spend(job_id: str, amount: float) -> None:
    """Job 완료 후 지출 기록 (dispatcher에서 호출)"""
    today = date.today().isoformat()
    await db.add_budget_spent(today, amount)
    logger.info("지출 기록 — Job %s: $%.4f", job_id, amount)

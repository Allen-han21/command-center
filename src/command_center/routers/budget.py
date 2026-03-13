"""Budget API"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from command_center import db
from command_center.models import Budget, BudgetUpdate

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("", response_model=Budget)
async def get_budget(target_date: str | None = None):
    budget = await db.get_budget(target_date)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.put("", response_model=Budget)
async def update_budget(body: BudgetUpdate, target_date: str | None = None):
    if target_date is None:
        target_date = date.today().isoformat()
    # 없으면 먼저 get으로 생성
    await db.get_budget(target_date)
    budget = await db.update_budget_limit(target_date, body.limit_usd)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget

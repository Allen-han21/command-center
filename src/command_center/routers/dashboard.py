"""Dashboard aggregate API"""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter

from command_center import db
from command_center.config import DEFAULT_TIME_SLOTS
from command_center.models import DashboardSummary
from command_center.services.integrator import get_sentinels, get_latest_rhythm

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _next_slot(slots: list[dict]) -> str | None:
    """현재 시각 기준 다음 활성 슬롯 이름 반환"""
    now = datetime.now().time()
    for slot in slots:
        if not slot["enabled"] or slot["name"] == "anytime":
            continue
        if slot["start_time"] is None:
            continue
        try:
            start = time.fromisoformat(slot["start_time"])
            if now < start:
                return slot["name"]
        except ValueError:
            continue
    return None


@router.get("", response_model=DashboardSummary)
async def get_dashboard():
    today = date.today().isoformat()

    all_jobs = await db.list_jobs()
    budget = await db.get_budget(today)
    slots = await db.list_time_slots()

    running = [j for j in all_jobs if j["status"] == "running"]
    queued = [j for j in all_jobs if j["status"] == "queued"]
    recent_completed = [
        j for j in all_jobs
        if j["status"] == "completed" and j.get("completed_at", "")[:10] == today
    ][-5:]
    failed = [j for j in all_jobs if j["status"] == "failed"]

    # Ecosystem integration
    sentinel_entries, _ = get_sentinels(pending_only=True, limit=100)
    rhythm = get_latest_rhythm()

    return DashboardSummary(
        running_jobs=len(running),
        queued_jobs=len(queued),
        today_spent_usd=budget["spent_usd"] if budget else 0.0,
        today_limit_usd=budget["limit_usd"] if budget else 10.0,
        today_job_count=budget["job_count"] if budget else 0,
        next_slot=_next_slot(slots),
        recent_completed=[{"id": j["id"], "title": j["title"], "completed_at": j.get("completed_at")} for j in recent_completed],
        failed_jobs=[{"id": j["id"], "title": j["title"], "error_message": j.get("error_message")} for j in failed],
        sentinels_pending=len(sentinel_entries),
        rhythm_cycle=rhythm.type if rhythm else None,
        rhythm_phase=rhythm.current_phase if rhythm else None,
    )

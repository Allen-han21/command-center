"""Job 스케줄러 - time_slot 매칭 + dependency 해결 + priority 정렬"""

from __future__ import annotations

import logging
from datetime import datetime, time

from command_center import db

logger = logging.getLogger(__name__)


async def pick_next_job() -> dict | None:
    """실행 가능한 다음 Job을 반환한다.

    선택 기준:
    1. 현재 활성 time_slot 확인
    2. max_concurrent 슬롯 여유 확인
    3. blocked_by 의존성 모두 완료된 queued Job
    4. priority ASC, created_at ASC 순 (list_jobs 기본 정렬)
    """
    active_slot = await _get_active_slot()
    if active_slot is None:
        logger.debug("활성 time_slot 없음")
        return None

    running_jobs = await db.list_jobs(status="running")
    if len(running_jobs) >= active_slot.get("max_concurrent", 1):
        logger.debug(
            "max_concurrent %d 도달 (현재 %d개 실행 중)",
            active_slot["max_concurrent"],
            len(running_jobs),
        )
        return None

    completed_ids = {j["id"] for j in await db.list_jobs(status="completed")}
    queued_jobs = await db.list_jobs(status="queued")

    for job in queued_jobs:
        if (
            _is_slot_match(job, active_slot)
            and _are_deps_resolved(job, completed_ids)
            and _is_scheduled_ready(job)
        ):
            return job

    return None


async def _get_active_slot() -> dict | None:
    """현재 시각에 enabled 상태인 time_slot 반환"""
    slots = await db.list_time_slots()
    now = datetime.now().time()
    for slot in slots:
        if slot.get("enabled") and _time_in_slot(now, slot):
            return slot
    return None


def _time_in_slot(now: time, slot: dict) -> bool:
    """현재 시각이 slot 범위 내인지 확인.

    start/end가 없으면 anytime으로 간주 (항상 True).
    midnight crossing (예: 22:00-08:00) 자동 처리.
    """
    start_str = slot.get("start_time")
    end_str = slot.get("end_time")

    if not start_str or not end_str:
        return True  # anytime

    start = _parse_time(start_str)
    end = _parse_time(end_str)

    if start <= end:
        return start <= now < end
    else:
        # midnight crossing: 22:00-08:00
        return now >= start or now < end


def _parse_time(t: str) -> time:
    h, m = t.split(":")
    return time(int(h), int(m))


def _is_slot_match(job: dict, active_slot: dict) -> bool:
    """Job의 time_slot이 활성 slot과 호환되는지 확인.

    - active_slot이 anytime이면 모든 job 허용
    - job의 time_slot이 anytime이면 어떤 slot에서도 실행 가능
    - 그 외엔 정확히 일치해야 함
    """
    job_slot = job.get("time_slot", "anytime")
    if active_slot["name"] == "anytime" or job_slot == "anytime":
        return True
    return job_slot == active_slot["name"]


def _is_scheduled_ready(job: dict) -> bool:
    """scheduled_at이 설정된 경우, 현재 시각이 그 이후인지 확인.

    scheduled_at이 None이면 항상 실행 가능.
    """
    scheduled_at = job.get("scheduled_at")
    if not scheduled_at:
        return True
    try:
        target = datetime.fromisoformat(scheduled_at)
        return datetime.now() >= target
    except (ValueError, TypeError):
        logger.warning("잘못된 scheduled_at 형식: %s (Job %s)", scheduled_at, job.get("id"))
        return True  # 파싱 실패 시 실행 허용 (blocking 방지)


def _are_deps_resolved(job: dict, completed_ids: set[str]) -> bool:
    """blocked_by의 모든 Job ID가 완료 목록에 있는지 확인"""
    blocked_by = job.get("blocked_by") or []
    return all(dep_id in completed_ids for dep_id in blocked_by)

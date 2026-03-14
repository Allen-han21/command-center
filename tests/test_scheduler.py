"""Level 1: Pure function tests + Level 3: Integration tests for scheduler."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
import pytest_asyncio

from command_center import db
from command_center.services.scheduler import (
    _are_deps_resolved,
    _is_scheduled_ready,
    _is_slot_match,
    _time_in_slot,
    pick_next_job,
)


# ── Level 1: _time_in_slot (pure function) ──


class TestTimeInSlot:
    def test_normal_range_inside(self):
        """12:30은 lunch(12:00-13:00) 안에 있다."""
        slot = {"start_time": "12:00", "end_time": "13:00"}
        assert _time_in_slot(time(12, 30), slot) is True

    def test_normal_range_outside(self):
        """14:00은 lunch(12:00-13:00) 밖이다."""
        slot = {"start_time": "12:00", "end_time": "13:00"}
        assert _time_in_slot(time(14, 0), slot) is False

    def test_normal_range_start_boundary(self):
        """12:00 정각은 포함 (start <= now)."""
        slot = {"start_time": "12:00", "end_time": "13:00"}
        assert _time_in_slot(time(12, 0), slot) is True

    def test_normal_range_end_boundary(self):
        """13:00 정각은 미포함 (now < end)."""
        slot = {"start_time": "12:00", "end_time": "13:00"}
        assert _time_in_slot(time(13, 0), slot) is False

    def test_midnight_crossing_night(self):
        """23:00은 sleep(22:00-08:00) 안에 있다."""
        slot = {"start_time": "22:00", "end_time": "08:00"}
        assert _time_in_slot(time(23, 0), slot) is True

    def test_midnight_crossing_early_morning(self):
        """03:00은 sleep(22:00-08:00) 안에 있다."""
        slot = {"start_time": "22:00", "end_time": "08:00"}
        assert _time_in_slot(time(3, 0), slot) is True

    def test_midnight_crossing_outside_afternoon(self):
        """15:00은 sleep(22:00-08:00) 밖이다."""
        slot = {"start_time": "22:00", "end_time": "08:00"}
        assert _time_in_slot(time(15, 0), slot) is False

    def test_midnight_crossing_end_boundary(self):
        """08:00 정각은 sleep(22:00-08:00) 밖이다."""
        slot = {"start_time": "22:00", "end_time": "08:00"}
        assert _time_in_slot(time(8, 0), slot) is False

    def test_midnight_crossing_start_boundary(self):
        """22:00 정각은 sleep(22:00-08:00) 안이다."""
        slot = {"start_time": "22:00", "end_time": "08:00"}
        assert _time_in_slot(time(22, 0), slot) is True

    def test_anytime_no_times(self):
        """start/end 없으면 항상 True (anytime)."""
        slot = {"start_time": None, "end_time": None}
        assert _time_in_slot(time(15, 0), slot) is True

    def test_anytime_empty_strings(self):
        """빈 문자열도 anytime으로 처리."""
        slot = {"start_time": "", "end_time": ""}
        assert _time_in_slot(time(15, 0), slot) is True


# ── Level 1: _is_slot_match (pure function) ──


class TestIsSlotMatch:
    def test_exact_match(self):
        job = {"time_slot": "lunch"}
        active = {"name": "lunch"}
        assert _is_slot_match(job, active) is True

    def test_no_match(self):
        job = {"time_slot": "sleep"}
        active = {"name": "lunch"}
        assert _is_slot_match(job, active) is False

    def test_job_anytime_matches_any_slot(self):
        """anytime job은 어떤 slot에서도 실행 가능."""
        job = {"time_slot": "anytime"}
        active = {"name": "sleep"}
        assert _is_slot_match(job, active) is True

    def test_active_anytime_matches_any_job(self):
        """active slot이 anytime이면 모든 job 허용."""
        job = {"time_slot": "sleep"}
        active = {"name": "anytime"}
        assert _is_slot_match(job, active) is True


# ── Level 1: _are_deps_resolved (pure function) ──


class TestAreDepsResolved:
    def test_no_deps(self):
        job = {"blocked_by": []}
        assert _are_deps_resolved(job, set()) is True

    def test_all_deps_completed(self):
        job = {"blocked_by": ["a", "b"]}
        assert _are_deps_resolved(job, {"a", "b", "c"}) is True

    def test_some_deps_pending(self):
        job = {"blocked_by": ["a", "b"]}
        assert _are_deps_resolved(job, {"a"}) is False

    def test_none_blocked_by(self):
        """blocked_by가 None이면 의존성 없음."""
        job = {"blocked_by": None}
        assert _are_deps_resolved(job, set()) is True


# ── Level 1: _is_scheduled_ready (pure function) ──


class TestIsScheduledReady:
    def test_no_scheduled_at(self):
        """scheduled_at이 None이면 항상 실행 가능."""
        assert _is_scheduled_ready({"scheduled_at": None}) is True

    def test_empty_string(self):
        """빈 문자열도 실행 가능."""
        assert _is_scheduled_ready({"scheduled_at": ""}) is True

    def test_past_time_ready(self):
        """과거 시각이면 실행 가능."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        assert _is_scheduled_ready({"scheduled_at": past}) is True

    def test_future_time_not_ready(self):
        """미래 시각이면 실행 불가."""
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        assert _is_scheduled_ready({"scheduled_at": future}) is False

    def test_invalid_format_returns_true(self):
        """파싱 불가 시 blocking 방지를 위해 True."""
        assert _is_scheduled_ready({"scheduled_at": "not-a-date"}) is True


# ── Level 3: pick_next_job (integration) ──


class TestPickNextJob:
    @pytest.mark.asyncio
    async def test_no_jobs_returns_none(self, init_test_db, monkeypatch):
        """큐가 비면 None."""
        # anytime을 활성화해야 pick이 동작
        await db.update_time_slot("anytime", {"enabled": True})
        result = await pick_next_job()
        assert result is None

    @pytest.mark.asyncio
    async def test_picks_highest_priority(self, init_test_db):
        """priority가 낮은(= 높은 우선순위) job을 먼저 선택."""
        await db.update_time_slot("anytime", {"enabled": True})
        await db.create_job({"title": "low", "prompt": "x", "priority": 8, "time_slot": "anytime"})
        await db.create_job({"title": "high", "prompt": "x", "priority": 1, "time_slot": "anytime"})

        job = await pick_next_job()
        assert job is not None
        assert job["title"] == "high"
        assert job["priority"] == 1

    @pytest.mark.asyncio
    async def test_blocked_job_skipped(self, init_test_db):
        """의존성 미해결 job은 건너뛴다."""
        await db.update_time_slot("anytime", {"enabled": True})
        await db.create_job({
            "title": "blocked",
            "prompt": "x",
            "priority": 1,
            "time_slot": "anytime",
            "blocked_by": ["nonexistent_id"],
        })
        await db.create_job({"title": "free", "prompt": "x", "priority": 5, "time_slot": "anytime"})

        job = await pick_next_job()
        assert job is not None
        assert job["title"] == "free"

    @pytest.mark.asyncio
    async def test_max_concurrent_blocks(self, init_test_db):
        """max_concurrent에 도달하면 None."""
        await db.update_time_slot("anytime", {"enabled": True, "max_concurrent": 1})
        # running job 하나 생성
        j = await db.create_job({"title": "running", "prompt": "x", "time_slot": "anytime"})
        await db.update_job(j["id"], {"status": "running"})
        # queued job도 하나
        await db.create_job({"title": "waiting", "prompt": "x", "time_slot": "anytime"})

        job = await pick_next_job()
        assert job is None

    @pytest.mark.asyncio
    async def test_scheduled_at_future_skipped(self, init_test_db):
        """scheduled_at이 미래인 job은 건너뛰고, 즉시 실행 가능한 job을 선택."""
        await db.update_time_slot("anytime", {"enabled": True})
        future = (datetime.now() + timedelta(hours=2)).isoformat()
        await db.create_job({
            "title": "future-job",
            "prompt": "x",
            "priority": 1,
            "time_slot": "anytime",
            "scheduled_at": future,
        })
        await db.create_job({"title": "now-job", "prompt": "x", "priority": 5, "time_slot": "anytime"})

        job = await pick_next_job()
        assert job is not None
        assert job["title"] == "now-job"

    @pytest.mark.asyncio
    async def test_scheduled_at_past_picked(self, init_test_db):
        """scheduled_at이 과거인 job은 정상적으로 선택."""
        await db.update_time_slot("anytime", {"enabled": True})
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        await db.create_job({
            "title": "past-scheduled",
            "prompt": "x",
            "priority": 1,
            "time_slot": "anytime",
            "scheduled_at": past,
        })

        job = await pick_next_job()
        assert job is not None
        assert job["title"] == "past-scheduled"

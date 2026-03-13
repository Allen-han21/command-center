"""Level 2: DB CRUD integration tests (in-memory SQLite via tmp_path)."""

from __future__ import annotations

import pytest

from command_center import db


@pytest.mark.asyncio
class TestJobCRUD:
    async def test_create_and_get(self, init_test_db):
        job = await db.create_job({"title": "Test", "prompt": "echo hi"})
        assert job["title"] == "Test"
        assert job["status"] == "queued"
        assert len(job["id"]) == 12  # nanoid

        fetched = await db.get_job(job["id"])
        assert fetched is not None
        assert fetched["title"] == "Test"

    async def test_list_filter_by_status(self, init_test_db):
        j1 = await db.create_job({"title": "A", "prompt": "x"})
        j2 = await db.create_job({"title": "B", "prompt": "x"})
        await db.update_job(j2["id"], {"status": "running"})

        queued = await db.list_jobs(status="queued")
        running = await db.list_jobs(status="running")

        assert len(queued) == 1
        assert queued[0]["id"] == j1["id"]
        assert len(running) == 1
        assert running[0]["id"] == j2["id"]

    async def test_list_sorted_by_priority(self, init_test_db):
        await db.create_job({"title": "low", "prompt": "x", "priority": 8})
        await db.create_job({"title": "high", "prompt": "x", "priority": 1})

        jobs = await db.list_jobs()
        assert jobs[0]["title"] == "high"
        assert jobs[1]["title"] == "low"

    async def test_update_fields(self, init_test_db):
        job = await db.create_job({"title": "Before", "prompt": "x"})
        updated = await db.update_job(job["id"], {"title": "After", "status": "running"})
        assert updated["title"] == "After"
        assert updated["status"] == "running"

    async def test_update_nonexistent_returns_none(self, init_test_db):
        result = await db.update_job("nonexistent", {"title": "x"})
        # update_job does get_job after update, which returns None
        # But the update itself doesn't fail — it just updates 0 rows
        # The get_job after returns None
        assert result is None

    async def test_delete(self, init_test_db):
        job = await db.create_job({"title": "Del", "prompt": "x"})
        assert await db.delete_job(job["id"]) is True
        assert await db.get_job(job["id"]) is None

    async def test_delete_nonexistent(self, init_test_db):
        assert await db.delete_job("nonexistent") is False

    async def test_blocked_by_roundtrip(self, init_test_db):
        """blocked_by JSON 직렬화/역직렬화."""
        job = await db.create_job({
            "title": "Blocked",
            "prompt": "x",
            "blocked_by": ["aaa", "bbb"],
        })
        assert job["blocked_by"] == ["aaa", "bbb"]

    async def test_use_worktree_bool(self, init_test_db):
        """use_worktree는 bool로 변환."""
        job = await db.create_job({"title": "WT", "prompt": "x", "use_worktree": True})
        assert job["use_worktree"] is True

    async def test_nanoid_uniqueness(self, init_test_db):
        """100개 Job의 ID가 모두 고유."""
        ids = set()
        for i in range(100):
            job = await db.create_job({"title": f"Job{i}", "prompt": "x"})
            ids.add(job["id"])
        assert len(ids) == 100


@pytest.mark.asyncio
class TestTimeSlotCRUD:
    async def test_default_slots_created(self, init_test_db):
        slots = await db.list_time_slots()
        names = {s["name"] for s in slots}
        assert names == {"sleep", "lunch", "commute", "anytime"}

    async def test_sleep_slot_values(self, init_test_db):
        slot = await db.get_time_slot("sleep")
        assert slot is not None
        assert slot["start_time"] == "22:00"
        assert slot["end_time"] == "08:00"
        assert slot["max_concurrent"] == 2
        assert slot["enabled"] is True

    async def test_anytime_disabled_by_default(self, init_test_db):
        slot = await db.get_time_slot("anytime")
        assert slot is not None
        assert slot["enabled"] is False

    async def test_update_slot(self, init_test_db):
        updated = await db.update_time_slot("lunch", {"enabled": False})
        assert updated is not None
        assert updated["enabled"] is False

    async def test_update_nonexistent(self, init_test_db):
        result = await db.update_time_slot("nonexistent", {"enabled": True})
        assert result is None


@pytest.mark.asyncio
class TestBudgetCRUD:
    async def test_auto_create_today(self, init_test_db):
        budget = await db.get_budget()
        assert budget is not None
        assert budget["spent_usd"] == 0.0
        assert budget["limit_usd"] == 10.0
        assert budget["remaining_usd"] == 10.0

    async def test_add_spending(self, init_test_db):
        from datetime import date
        today = date.today().isoformat()
        await db.add_budget_spent(today, 3.5)
        budget = await db.get_budget(today)
        assert budget["spent_usd"] == 3.5
        assert budget["remaining_usd"] == 6.5
        assert budget["job_count"] == 1

    async def test_cumulative_spending(self, init_test_db):
        from datetime import date
        today = date.today().isoformat()
        await db.add_budget_spent(today, 2.0)
        await db.add_budget_spent(today, 3.0)
        budget = await db.get_budget(today)
        assert budget["spent_usd"] == 5.0
        assert budget["job_count"] == 2

    async def test_update_limit(self, init_test_db):
        from datetime import date
        today = date.today().isoformat()
        updated = await db.update_budget_limit(today, 20.0)
        assert updated is not None
        assert updated["limit_usd"] == 20.0

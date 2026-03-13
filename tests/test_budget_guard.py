"""Level 3: Budget guard integration tests."""

from __future__ import annotations

from datetime import date

import pytest

from command_center import db
from command_center.services.budget_guard import can_spend, record_spend


@pytest.mark.asyncio
class TestCanSpend:
    async def test_within_budget(self, init_test_db):
        """한도 내 금액은 허용."""
        assert await can_spend(2.0) is True

    async def test_exact_budget(self, init_test_db):
        """한도와 정확히 같은 금액은 허용."""
        assert await can_spend(10.0) is True

    async def test_over_budget(self, init_test_db):
        """한도 초과 금액은 거부."""
        assert await can_spend(11.0) is False

    async def test_after_spending(self, init_test_db):
        """기존 지출 후 잔여 예산만큼만 허용."""
        today = date.today().isoformat()
        await db.add_budget_spent(today, 8.0)
        assert await can_spend(2.0) is True
        assert await can_spend(3.0) is False


@pytest.mark.asyncio
class TestRecordSpend:
    async def test_record_updates_budget(self, init_test_db):
        today = date.today().isoformat()
        await record_spend("job123", 3.5)
        budget = await db.get_budget(today)
        assert budget["spent_usd"] == 3.5
        assert budget["job_count"] == 1

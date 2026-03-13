"""Level 3+: Dispatcher E2E tests.

dispatcher.main()의 전체 파이프라인을 검증한다.
실 DB를 사용하되, run_job만 mock하여 claude 실행을 건너뛴다.

검증 대상:
- pick_next_job → can_spend → run_job → record_spend 체인의 정확한 동작
- 예산 부족 시 실행 건너뛰기
- Job이 없을 때 깔끔한 종료
- 성공 시 지출 기록, 실패 시 미기록
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from command_center import db
from command_center.dispatcher import main as dispatcher_main


@pytest.mark.asyncio
async def test_no_jobs_exits_cleanly(init_test_db):
    """큐에 Job이 없으면 아무 것도 실행하지 않고 종료."""
    # anytime 활성화
    await db.update_time_slot("anytime", {"enabled": True})

    with patch("command_center.dispatcher.run_job", new_callable=AsyncMock) as mock_run:
        await dispatcher_main()

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_picks_and_runs_job(init_test_db):
    """큐에 Job이 있으면 pick → can_spend → run_job → record_spend 순서로 실행.

    run_job을 mock하되, DB에서 status를 completed로 수동 전환하여
    dispatcher가 record_spend까지 호출하도록 한다.
    """
    await db.update_time_slot("anytime", {"enabled": True})
    job = await db.create_job({
        "title": "Dispatch Test",
        "prompt": "hello",
        "time_slot": "anytime",
        "max_budget": 1.5,
    })

    async def fake_run_job(j):
        """run_job의 가짜: DB에 completed 상태만 기록."""
        await db.update_job(j["id"], {"status": "completed"})

    with patch("command_center.dispatcher.run_job", side_effect=fake_run_job):
        await dispatcher_main()

    # Job이 completed 상태인지 확인
    finished = await db.get_job(job["id"])
    assert finished["status"] == "completed"

    # 지출이 기록되었는지 확인
    today = date.today().isoformat()
    budget = await db.get_budget(today)
    assert budget["spent_usd"] == 1.5
    assert budget["job_count"] == 1


@pytest.mark.asyncio
async def test_budget_insufficient_skips(init_test_db):
    """예산이 부족하면 Job을 실행하지 않는다.

    시나리오: 한도 $10, 이미 $9.5 소진, Job은 $2 필요 → 스킵
    """
    await db.update_time_slot("anytime", {"enabled": True})
    today = date.today().isoformat()
    await db.add_budget_spent(today, 9.5)  # $10 중 $9.5 소진

    await db.create_job({
        "title": "Expensive",
        "prompt": "x",
        "time_slot": "anytime",
        "max_budget": 2.0,  # $2 필요하지만 $0.5만 남음
    })

    with patch("command_center.dispatcher.run_job", new_callable=AsyncMock) as mock_run:
        await dispatcher_main()

    mock_run.assert_not_called()

    # 예산 변동 없음
    budget = await db.get_budget(today)
    assert budget["spent_usd"] == 9.5  # 변동 없음


@pytest.mark.asyncio
async def test_failed_job_no_spend_recorded(init_test_db):
    """run_job 실행 후 Job이 failed 상태면 지출을 기록하지 않는다.

    이유: record_spend는 status=="completed" 조건에서만 호출됨.
    """
    await db.update_time_slot("anytime", {"enabled": True})
    job = await db.create_job({
        "title": "Fail Dispatch",
        "prompt": "x",
        "time_slot": "anytime",
        "max_budget": 3.0,
        "max_retries": 0,  # retry 없음 → 바로 failed
    })

    async def fake_run_job_fail(j):
        """실패를 시뮬레이션: status를 queued로 되돌림 (retry가 있을 때)
        또는 failed로 전환."""
        await db.update_job(j["id"], {
            "status": "failed",
            "error_message": "mock failure",
        })

    with patch("command_center.dispatcher.run_job", side_effect=fake_run_job_fail):
        await dispatcher_main()

    # Job은 failed
    finished = await db.get_job(job["id"])
    assert finished["status"] == "failed"

    # 지출 미기록
    today = date.today().isoformat()
    budget = await db.get_budget(today)
    assert budget["spent_usd"] == 0.0
    assert budget["job_count"] == 0


@pytest.mark.asyncio
async def test_priority_ordering(init_test_db):
    """여러 Job이 있을 때 priority가 높은(숫자 낮은) Job부터 실행."""
    await db.update_time_slot("anytime", {"enabled": True})

    await db.create_job({"title": "Low P", "prompt": "x", "priority": 8, "time_slot": "anytime"})
    high = await db.create_job({"title": "High P", "prompt": "x", "priority": 1, "time_slot": "anytime"})

    executed_ids = []

    async def fake_run_job(j):
        executed_ids.append(j["id"])
        await db.update_job(j["id"], {"status": "completed"})

    with patch("command_center.dispatcher.run_job", side_effect=fake_run_job):
        await dispatcher_main()

    # dispatcher는 1회 실행 시 job 1개만 처리
    assert len(executed_ids) == 1
    assert executed_ids[0] == high["id"]  # priority 1이 먼저


@pytest.mark.asyncio
async def test_dependency_blocks_execution(init_test_db):
    """blocked_by가 미완료인 Job은 건너뛰고, 해결된 Job을 실행."""
    await db.update_time_slot("anytime", {"enabled": True})

    dep = await db.create_job({"title": "Dep", "prompt": "x", "priority": 5, "time_slot": "anytime"})
    await db.create_job({
        "title": "Blocked",
        "prompt": "x",
        "priority": 1,  # 이게 priority 더 높지만 의존성 미해결
        "time_slot": "anytime",
        "blocked_by": [dep["id"]],
    })
    free = await db.create_job({"title": "Free", "prompt": "x", "priority": 3, "time_slot": "anytime"})

    executed_ids = []

    async def fake_run_job(j):
        executed_ids.append(j["id"])
        await db.update_job(j["id"], {"status": "completed"})

    with patch("command_center.dispatcher.run_job", side_effect=fake_run_job):
        await dispatcher_main()

    # Blocked는 건너뛰고 Free를 실행 (Dep보다 priority 높음)
    assert executed_ids == [free["id"]]

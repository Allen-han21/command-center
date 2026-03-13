"""Level 3: executor.run_job mock tests.

실제 claude CLI를 실행하지 않고, subprocess를 가짜로 대체하여
run_job의 DB 상태 전환 로직을 검증한다.

Mock 대상: asyncio.create_subprocess_exec
검증 대상: DB 상태 전환 (running → completed/failed), retry 로직, 출력 파일 저장
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from command_center import db
from command_center.services import executor
from command_center.services.executor import run_job


def _make_fake_process(
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    pid: int = 99999,
):
    """가짜 asyncio.subprocess.Process 생성.

    communicate()를 호출하면 미리 정의된 stdout/stderr를 반환하고,
    returncode를 설정한 값으로 세팅한다.
    """
    proc = AsyncMock(spec=asyncio.subprocess.Process)
    proc.pid = pid
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ── 성공 시나리오 ──


@pytest.mark.asyncio
async def test_run_job_success(init_test_db, tmp_path, monkeypatch):
    """claude가 returncode=0을 반환하면:
    1. DB status → "running" → "completed"
    2. result_summary가 추출됨
    3. pid가 None으로 정리됨
    4. 출력 파일이 저장됨
    """
    # OUTPUT_DIR을 tmp_path로 패치 (실제 파일 쓰기 검증용)
    monkeypatch.setattr(executor, "OUTPUT_DIR", tmp_path)

    # 테스트 Job 생성
    job = await db.create_job({"title": "Success Test", "prompt": "hello"})
    assert job["status"] == "queued"

    # 가짜 프로세스: returncode=0, stream-json result 출력
    fake_stdout = json.dumps({"type": "result", "result": "All done!"}).encode() + b"\n"
    fake_proc = _make_fake_process(returncode=0, stdout=fake_stdout)

    with patch("command_center.services.executor.asyncio") as mock_asyncio:
        # asyncio.create_subprocess_exec만 mock, timeout은 실제 사용
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=fake_proc)
        mock_asyncio.subprocess = asyncio.subprocess
        mock_asyncio.timeout = asyncio.timeout

        await run_job(job)

    # DB 검증
    finished = await db.get_job(job["id"])
    assert finished["status"] == "completed"
    assert finished["result_summary"] == "All done!"
    assert finished["pid"] is None
    assert finished["started_at"] is not None
    assert finished["completed_at"] is not None

    # 출력 파일 검증
    output_file = tmp_path / f"{job['id']}.jsonl"
    assert output_file.exists()
    assert b"All done!" in output_file.read_bytes()


# ── 실패 → retry 시나리오 ──


@pytest.mark.asyncio
async def test_run_job_failure_triggers_retry(init_test_db, tmp_path, monkeypatch):
    """claude가 returncode=1을 반환하고 retry 여유가 있으면:
    1. status → "queued" (retry를 위해 다시 큐에)
    2. retry_count가 1 증가
    3. error_message에 "[retry N/M]" 포맷
    """
    monkeypatch.setattr(executor, "OUTPUT_DIR", tmp_path)

    job = await db.create_job({
        "title": "Fail Test",
        "prompt": "x",
        "max_retries": 2,  # 2번까지 재시도 가능
    })

    fake_proc = _make_fake_process(returncode=1, stderr=b"Something went wrong")

    with patch("command_center.services.executor.asyncio") as mock_asyncio:
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=fake_proc)
        mock_asyncio.subprocess = asyncio.subprocess
        mock_asyncio.timeout = asyncio.timeout

        await run_job(job)

    finished = await db.get_job(job["id"])
    assert finished["status"] == "queued"  # 재시도를 위해 다시 큐에
    assert finished["retry_count"] == 1
    assert "[retry 1/2]" in finished["error_message"]
    assert "Something went wrong" in finished["error_message"]


# ── 실패 → retry 소진 시나리오 ──


@pytest.mark.asyncio
async def test_run_job_failure_exhausts_retries(init_test_db, tmp_path, monkeypatch):
    """retry_count가 이미 max_retries에 도달한 상태에서 또 실패하면:
    1. status → "failed" (더 이상 재시도 안함)
    2. completed_at이 설정됨
    """
    monkeypatch.setattr(executor, "OUTPUT_DIR", tmp_path)

    job = await db.create_job({
        "title": "Exhausted",
        "prompt": "x",
        "max_retries": 1,
    })
    # retry_count를 이미 1로 설정 (1번 실패한 상태)
    await db.update_job(job["id"], {"retry_count": 1})
    # run_job은 원래 job dict를 사용하므로, retry_count를 반영
    job["retry_count"] = 1

    fake_proc = _make_fake_process(returncode=1, stderr=b"Fatal error")

    with patch("command_center.services.executor.asyncio") as mock_asyncio:
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=fake_proc)
        mock_asyncio.subprocess = asyncio.subprocess
        mock_asyncio.timeout = asyncio.timeout

        await run_job(job)

    finished = await db.get_job(job["id"])
    assert finished["status"] == "failed"
    assert finished["completed_at"] is not None
    assert "Fatal error" in finished["error_message"]


# ── 빈 stdout 성공 ──


@pytest.mark.asyncio
async def test_run_job_success_empty_stdout(init_test_db, tmp_path, monkeypatch):
    """stdout이 비어있어도 returncode=0이면 completed.
    result_summary는 빈 문자열.
    """
    monkeypatch.setattr(executor, "OUTPUT_DIR", tmp_path)

    job = await db.create_job({"title": "Empty", "prompt": "x"})

    fake_proc = _make_fake_process(returncode=0, stdout=b"")

    with patch("command_center.services.executor.asyncio") as mock_asyncio:
        mock_asyncio.create_subprocess_exec = AsyncMock(return_value=fake_proc)
        mock_asyncio.subprocess = asyncio.subprocess
        mock_asyncio.timeout = asyncio.timeout

        await run_job(job)

    finished = await db.get_job(job["id"])
    assert finished["status"] == "completed"
    assert finished["result_summary"] == ""

    # 빈 stdout이면 출력 파일 미생성
    output_file = tmp_path / f"{job['id']}.jsonl"
    assert not output_file.exists()


# ── 예외 발생 시나리오 ──


@pytest.mark.asyncio
async def test_run_job_exception_handling(init_test_db, tmp_path, monkeypatch):
    """subprocess 생성 자체가 실패하면 (예: claude 미설치):
    _handle_failure를 통해 retry 또는 failed 처리.
    """
    monkeypatch.setattr(executor, "OUTPUT_DIR", tmp_path)

    job = await db.create_job({"title": "Exception", "prompt": "x"})

    with patch("command_center.services.executor.asyncio") as mock_asyncio:
        mock_asyncio.create_subprocess_exec = AsyncMock(
            side_effect=FileNotFoundError("claude: command not found")
        )
        mock_asyncio.subprocess = asyncio.subprocess
        mock_asyncio.timeout = asyncio.timeout

        await run_job(job)

    finished = await db.get_job(job["id"])
    # retry 여유가 있으므로 queued로 복귀
    assert finished["status"] == "queued"
    assert "command not found" in finished["error_message"]

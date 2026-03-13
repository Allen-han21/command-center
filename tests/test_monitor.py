"""monitor.py + sessions router 테스트"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from command_center.services.monitor import (
    ConnectionManager,
    _build_session_snapshot,
    _discover_claude_pids,
    notify_job_complete,
)


# ── ConnectionManager ──


@pytest.mark.asyncio
async def test_manager_connect_disconnect():
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws)
    assert mgr.count == 1
    ws.accept.assert_awaited_once()

    mgr.disconnect(ws)
    assert mgr.count == 0


@pytest.mark.asyncio
async def test_manager_broadcast():
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    await mgr.broadcast({"type": "test", "data": 42})
    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()

    msg1 = json.loads(ws1.send_text.call_args[0][0])
    assert msg1 == {"type": "test", "data": 42}


@pytest.mark.asyncio
async def test_manager_broadcast_removes_dead():
    mgr = ConnectionManager()
    alive = AsyncMock()
    dead = AsyncMock()
    dead.send_text.side_effect = RuntimeError("connection closed")

    await mgr.connect(alive)
    await mgr.connect(dead)
    assert mgr.count == 2

    await mgr.broadcast({"type": "ping"})
    assert mgr.count == 1  # dead removed


# ── Process Discovery ──


@pytest.mark.asyncio
async def test_discover_claude_pids_empty():
    """pgrep 결과 없음 → 빈 set"""
    with patch("command_center.services.monitor.asyncio.create_subprocess_exec") as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        mock_exec.return_value = proc

        pids = await _discover_claude_pids()
        assert pids == set()


@pytest.mark.asyncio
async def test_discover_claude_pids_found():
    """pgrep 결과 있음 → PID set"""
    with patch("command_center.services.monitor.asyncio.create_subprocess_exec") as mock_exec:
        proc = AsyncMock()
        proc.communicate.return_value = (b"12345\n67890\n", b"")
        mock_exec.return_value = proc

        pids = await _discover_claude_pids()
        assert pids == {12345, 67890}


# ── Session Snapshot ──


@pytest.mark.asyncio
async def test_build_session_snapshot_no_running(tmp_path, monkeypatch):
    """running job 없으면 빈 리스트"""
    from command_center import config, db as db_mod
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    from command_center import db
    await db.init_db()

    snapshot = await _build_session_snapshot()
    assert snapshot == []


@pytest.mark.asyncio
async def test_build_session_snapshot_with_job(tmp_path, monkeypatch):
    """running job이 있으면 스냅샷에 포함"""
    from command_center import config, db as db_mod
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")
    from command_center import db
    await db.init_db()

    job = await db.create_job({
        "title": "Test Job",
        "prompt": "echo test",
        "work_dir": "~",
    })
    await db.update_job(job["id"], {"status": "running", "pid": 99999})

    with patch("command_center.services.monitor._discover_claude_pids", return_value={99999}):
        snapshot = await _build_session_snapshot()

    assert len(snapshot) == 1
    assert snapshot[0]["job_id"] == job["id"]
    assert snapshot[0]["alive"] is True
    assert snapshot[0]["pid"] == 99999


# ── Desktop Notification ──


@pytest.mark.asyncio
async def test_notify_job_complete():
    """osascript 호출이 에러 없이 실행"""
    with patch("command_center.services.monitor.asyncio.create_subprocess_exec") as mock_exec:
        proc = AsyncMock()
        mock_exec.return_value = proc
        await notify_job_complete("My Job", "completed")
        mock_exec.assert_awaited_once()
        # osascript -e 'display notification ...'
        args = mock_exec.call_args[0]
        assert args[0] == "osascript"


# ── Sessions REST API ──


@pytest.mark.asyncio
async def test_sessions_api_empty(tmp_path, monkeypatch):
    from command_center import config, db as db_mod
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")

    from httpx import ASGITransport, AsyncClient
    from command_center.main import app
    from command_center import db
    await db.init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_sessions_api_with_running(tmp_path, monkeypatch):
    from command_center import config, db as db_mod
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / "test.db")

    from httpx import ASGITransport, AsyncClient
    from command_center.main import app
    from command_center import db
    await db.init_db()

    job = await db.create_job({"title": "Running", "prompt": "test", "work_dir": "~"})
    await db.update_job(job["id"], {"status": "running", "pid": 11111})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pid"] == 11111

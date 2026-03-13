"""Test configuration — temp DB per test, patched config paths."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

from command_center import config, db


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """모든 테스트에서 임시 DB를 사용하도록 config를 패치."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", test_db)
    # db 모듈이 config를 직접 임포트하므로 db 모듈 내부도 패치
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)


@pytest_asyncio.fixture
async def init_test_db():
    """DB 초기화 + 기본 time_slots + 오늘 budget 생성."""
    await db.init_db()

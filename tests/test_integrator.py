"""integrator.py 테스트 — sentinel/rhythm/pr-watch 읽기"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from command_center.services import integrator


@pytest.fixture
def mock_claude_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """~/.claude를 tmp_path로 대체"""
    claude_dir = tmp_path / ".claude"
    sentinel_dir = claude_dir / "sentinel"
    rhythm_dir = claude_dir / "rhythm"
    pr_watch_dir = claude_dir / "pr-watch"

    sentinel_dir.mkdir(parents=True, exist_ok=True)
    rhythm_dir.mkdir(parents=True, exist_ok=True)
    pr_watch_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(integrator, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(integrator, "SENTINEL_DIR", sentinel_dir)
    monkeypatch.setattr(integrator, "RHYTHM_DIR", rhythm_dir)
    monkeypatch.setattr(integrator, "PR_WATCH_STATE", pr_watch_dir / "state.json")

    return claude_dir


def _write_sentinel(sentinel_dir: Path, session_id: str, **overrides) -> Path:
    data = {
        "version": "1.0",
        "session_id": session_id,
        "project_id": overrides.get("project_id", "test-project"),
        "timestamp": overrides.get("timestamp", "2026-03-14T10:00:00+09:00"),
        "project": {"name": overrides.get("name", "Test Project")},
        "workflow_state": {
            "current_phase": overrides.get("current_phase", "impl"),
        },
        "pending_work": overrides.get("pending_work", ["task1", "task2"]),
    }
    if "ticket_id" in overrides:
        data["ticket_id"] = overrides["ticket_id"]
    path = sentinel_dir / f"{session_id}.json"
    path.write_text(json.dumps(data))
    return path


# ── Sentinel tests ──


def test_get_sentinels_empty(mock_claude_dir):
    entries, total = integrator.get_sentinels()
    assert entries == []
    assert total == 0


def test_get_sentinels_parses_files(mock_claude_dir):
    sentinel_dir = mock_claude_dir / "sentinel"
    _write_sentinel(sentinel_dir, "2026-03-14-test-CP1", name="My Project", pending_work=["a", "b", "c"])
    _write_sentinel(sentinel_dir, "2026-03-13-test-CP1", name="Old Project", current_phase="completed")

    # pending_only=True (default): completed 제외
    entries, total = integrator.get_sentinels(pending_only=True)
    assert total == 2
    assert len(entries) == 1
    assert entries[0].session_id == "2026-03-14-test-CP1"
    assert entries[0].name == "My Project"
    assert entries[0].pending_count == 3

    # pending_only=False: 전체
    entries, total = integrator.get_sentinels(pending_only=False)
    assert len(entries) == 2


def test_get_sentinels_limit(mock_claude_dir):
    sentinel_dir = mock_claude_dir / "sentinel"
    for i in range(5):
        _write_sentinel(sentinel_dir, f"2026-03-{10+i:02d}-test-CP1")

    entries, total = integrator.get_sentinels(pending_only=False, limit=3)
    assert total == 5
    assert len(entries) == 3


def test_get_sentinels_work_detection(mock_claude_dir):
    sentinel_dir = mock_claude_dir / "sentinel"
    _write_sentinel(sentinel_dir, "2026-03-14-PK-99999-CP1", ticket_id="PK-99999")
    _write_sentinel(sentinel_dir, "2026-03-14-personal-CP1", project_id="personal")

    entries, _ = integrator.get_sentinels(pending_only=False)
    work_entries = [e for e in entries if e.is_work]
    personal_entries = [e for e in entries if not e.is_work]
    assert len(work_entries) == 1
    assert len(personal_entries) == 1


def test_get_sentinels_corrupted_file(mock_claude_dir):
    sentinel_dir = mock_claude_dir / "sentinel"
    (sentinel_dir / "bad.json").write_text("not json{{{")
    _write_sentinel(sentinel_dir, "2026-03-14-good-CP1")

    entries, total = integrator.get_sentinels(pending_only=False)
    assert total == 2  # counts files
    assert len(entries) == 1  # skips bad


def test_sentinel_name_fallback(mock_claude_dir):
    """project.name이 없으면 resume_instructions.summary로 fallback"""
    sentinel_dir = mock_claude_dir / "sentinel"
    data = {
        "session_id": "2026-03-14-fallback-CP1",
        "project_id": "fallback",
        "timestamp": "2026-03-14T10:00:00+09:00",
        "workflow_state": {"current_phase": "impl"},
        "resume_instructions": {"summary": "Phase 4 완료, Phase 5 시작 대기"},
        "pending_work": [],
    }
    (sentinel_dir / "2026-03-14-fallback-CP1.json").write_text(json.dumps(data))

    entries, _ = integrator.get_sentinels(pending_only=False)
    assert entries[0].name == "Phase 4 완료, Phase 5 시작 대기"


# ── Rhythm tests ──


def test_get_latest_rhythm_empty(mock_claude_dir):
    assert integrator.get_latest_rhythm() is None


def test_get_latest_rhythm(mock_claude_dir):
    rhythm_dir = mock_claude_dir / "rhythm"
    data = {
        "version": "1.0",
        "cycle_id": "rhythm-2026-03-14-1",
        "date": "2026-03-14",
        "type": "dev-task",
        "started_at": "2026-03-14T09:00:00+09:00",
        "phases": {
            "warmup": {"started_at": "2026-03-14T09:00:00+09:00", "completed_at": "2026-03-14T09:15:00+09:00"},
            "deep_work": {"started_at": "2026-03-14T09:15:00+09:00"},
            "cooldown": {},
        },
    }
    (rhythm_dir / "rhythm-2026-03-14-1.json").write_text(json.dumps(data))

    result = integrator.get_latest_rhythm()
    assert result is not None
    assert result.type == "dev-task"
    assert result.current_phase == "deep_work"


# ── PR Watch tests ──


def test_get_pr_watch_not_found(mock_claude_dir):
    # state.json doesn't exist
    (mock_claude_dir / "pr-watch" / "state.json").unlink(missing_ok=True)
    assert integrator.get_pr_watch() is None


def test_get_pr_watch(mock_claude_dir):
    data = {
        "last_check": "2026-03-14T08:00:00+09:00",
        "reviewed_prs": {"PR-1": True, "PR-2": True},
        "pending_prs": [{"number": 123, "title": "Fix bug"}],
    }
    (mock_claude_dir / "pr-watch" / "state.json").write_text(json.dumps(data))

    result = integrator.get_pr_watch()
    assert result is not None
    assert result.reviewed_count == 2
    assert len(result.pending_prs) == 1


# ── Ecosystem summary ──


def test_get_ecosystem_summary(mock_claude_dir):
    sentinel_dir = mock_claude_dir / "sentinel"
    _write_sentinel(sentinel_dir, "2026-03-14-test-CP1")

    summary = integrator.get_ecosystem_summary()
    assert summary.sentinels_total == 1
    assert len(summary.sentinels_pending) == 1
    assert summary.rhythm is None
    assert summary.pr_watch is None

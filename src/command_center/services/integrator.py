"""Dominium 생태계 통합 읽기 서비스

~/.claude/{sentinel, rhythm, pr-watch} 파일을 읽어서
대시보드에 표시할 수 있는 요약 데이터를 반환한다.
모든 접근은 읽기 전용이며, 원본 파일을 수정하지 않는다.
"""

from __future__ import annotations

import json
import logging
from glob import glob
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── 경로 ──

CLAUDE_DIR = Path.home() / ".claude"
SENTINEL_DIR = CLAUDE_DIR / "sentinel"
RHYTHM_DIR = CLAUDE_DIR / "rhythm"
PR_WATCH_STATE = CLAUDE_DIR / "pr-watch" / "state.json"


# ── 모델 ──


class SentinelEntry(BaseModel):
    session_id: str
    project_id: str | None = None
    ticket_id: str | None = None
    name: str = ""
    current_phase: str = ""
    pending_count: int = 0
    timestamp: str = ""
    is_work: bool = False


class RhythmState(BaseModel):
    cycle_id: str = ""
    date: str = ""
    type: str = ""
    started_at: str = ""
    current_phase: str = ""
    phases: dict = {}


class PrWatchState(BaseModel):
    last_check: str = ""
    reviewed_count: int = 0
    pending_prs: list[dict] = []


class EcosystemSummary(BaseModel):
    sentinels_pending: list[SentinelEntry] = []
    sentinels_total: int = 0
    rhythm: RhythmState | None = None
    pr_watch: PrWatchState | None = None


# ── Sentinel ──

COMPLETED_PHASES = {"completed", "pr_complete"}


def _parse_sentinel(path: Path) -> SentinelEntry | None:
    """Sentinel JSON 파일에서 요약 정보를 추출한다."""
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    session_id = data.get("session_id", path.stem)
    project_id = data.get("project_id", data.get("ticket_id", ""))
    ticket_id = data.get("ticket_id")

    # 이름 추출 (우선순위: project.name > resume_instructions.summary > key_decisions[0])
    name = ""
    if isinstance(data.get("project"), dict):
        name = data["project"].get("name", "")
    if not name:
        ri = data.get("resume_instructions")
        if isinstance(ri, dict):
            name = ri.get("summary", "")[:80]
    if not name:
        kd = data.get("context_summary", {}).get("key_decisions", [])
        if kd and isinstance(kd[0], str):
            name = kd[0][:80]

    # phase (일부 파일에서 int로 저장된 경우 대비)
    ws = data.get("workflow_state", {})
    current_phase = str(ws.get("current_phase", data.get("checkpoint", "")))

    # pending count
    pending = data.get("pending_work", data.get("task_state", {}).get("pending_tasks", []))
    pending_count = len(pending) if isinstance(pending, list) else 0

    return SentinelEntry(
        session_id=session_id,
        project_id=project_id,
        ticket_id=ticket_id,
        name=name,
        current_phase=current_phase,
        pending_count=pending_count,
        timestamp=data.get("timestamp", data.get("created_at", "")),
        is_work=bool(ticket_id and "PK-" in str(ticket_id)),
    )


def get_sentinels(*, pending_only: bool = True, limit: int = 20) -> tuple[list[SentinelEntry], int]:
    """Sentinel 파일 목록을 반환한다. (최근순, 기본: pending만)"""
    if not SENTINEL_DIR.exists():
        return [], 0

    paths = sorted(SENTINEL_DIR.glob("*.json"), reverse=True)
    total = len(paths)
    entries: list[SentinelEntry] = []

    for p in paths:
        entry = _parse_sentinel(p)
        if entry is None:
            continue
        if pending_only and entry.current_phase in COMPLETED_PHASES:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries, total


# ── Rhythm ──


def get_latest_rhythm() -> RhythmState | None:
    """가장 최근 rhythm 파일을 읽어 반환한다."""
    if not RHYTHM_DIR.exists():
        return None

    files = sorted(RHYTHM_DIR.glob("rhythm-*.json"), reverse=True)
    if not files:
        return None

    try:
        data = json.loads(files[0].read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # 현재 phase 결정: status=in_progress 우선, 없으면 마지막 started_at
    phases = data.get("phases", {})
    current_phase = ""
    if isinstance(phases, dict):
        for phase_name, phase_data in phases.items():
            if isinstance(phase_data, dict):
                if phase_data.get("status") == "in_progress":
                    current_phase = phase_name
                    break
                if phase_data.get("started_at"):
                    current_phase = phase_name

    return RhythmState(
        cycle_id=data.get("cycle_id", ""),
        date=data.get("date", ""),
        type=data.get("type", ""),
        started_at=data.get("started_at", ""),
        current_phase=current_phase,
        phases=phases,
    )


# ── PR Watch ──


def get_pr_watch() -> PrWatchState | None:
    """PR watch 상태 파일을 읽어 반환한다."""
    if not PR_WATCH_STATE.exists():
        return None

    try:
        data = json.loads(PR_WATCH_STATE.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    reviewed = data.get("reviewed_prs", {})
    return PrWatchState(
        last_check=data.get("last_check", ""),
        reviewed_count=len(reviewed) if isinstance(reviewed, dict) else 0,
        pending_prs=data.get("pending_prs", []),
    )


# ── 통합 ──


def get_ecosystem_summary() -> EcosystemSummary:
    """전체 생태계 요약을 반환한다."""
    sentinels, total = get_sentinels(pending_only=True, limit=10)
    return EcosystemSummary(
        sentinels_pending=sentinels,
        sentinels_total=total,
        rhythm=get_latest_rhythm(),
        pr_watch=get_pr_watch(),
    )

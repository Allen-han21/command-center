"""SQLite 데이터베이스 - jobs, time_slots, budget"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

import aiosqlite

from command_center.config import DATA_DIR, DB_PATH, DEFAULT_TIME_SLOTS, DAILY_BUDGET_USD

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    work_dir TEXT NOT NULL DEFAULT '~',
    status TEXT NOT NULL DEFAULT 'queued',
    blocked_by TEXT NOT NULL DEFAULT '[]',
    priority INTEGER NOT NULL DEFAULT 5,
    time_slot TEXT NOT NULL DEFAULT 'anytime',
    scheduled_at TEXT,
    max_budget REAL NOT NULL DEFAULT 2.0,
    timeout_min INTEGER NOT NULL DEFAULT 30,
    model TEXT NOT NULL DEFAULT 'sonnet',
    effort TEXT NOT NULL DEFAULT 'high',
    use_worktree INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    pid INTEGER,
    result_summary TEXT,
    output_path TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    jira_ticket TEXT,
    parent_job_id TEXT,
    resume_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS time_slots (
    name TEXT PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    max_concurrent INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    days TEXT NOT NULL DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]'
);

CREATE TABLE IF NOT EXISTS budget (
    date TEXT PRIMARY KEY,
    limit_usd REAL NOT NULL DEFAULT 10.0,
    spent_usd REAL NOT NULL DEFAULT 0.0,
    job_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_time_slot ON jobs(time_slot);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
"""


async def init_db() -> None:
    """DB 초기화 + 기본 데이터 삽입"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)

        # 마이그레이션: 기존 DB에 새 컬럼 추가
        for col in ("parent_job_id TEXT", "resume_session_id TEXT"):
            try:
                await db.execute(f"ALTER TABLE jobs ADD COLUMN {col}")
            except Exception:
                pass  # 이미 존재하면 무시

        # 기본 time_slot 삽입
        cursor = await db.execute("SELECT COUNT(*) FROM time_slots")
        row = await cursor.fetchone()
        if row and row[0] == 0:
            for slot in DEFAULT_TIME_SLOTS:
                days_json = json.dumps(["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
                await db.execute(
                    """INSERT OR IGNORE INTO time_slots
                       (name, start_time, end_time, max_concurrent, enabled, days)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        slot["name"],
                        slot["start_time"],
                        slot["end_time"],
                        slot["max_concurrent"],
                        1 if slot["enabled"] else 0,
                        days_json,
                    ),
                )
            await db.commit()
            logger.info("기본 time_slot %d개 삽입", len(DEFAULT_TIME_SLOTS))

        # 오늘 예산 레코드 확인/삽입
        today = date.today().isoformat()
        cursor = await db.execute("SELECT COUNT(*) FROM budget WHERE date = ?", (today,))
        row = await cursor.fetchone()
        if row and row[0] == 0:
            await db.execute(
                "INSERT INTO budget (date, limit_usd) VALUES (?, ?)",
                (today, DAILY_BUDGET_USD),
            )
            await db.commit()


def _get_db():
    return aiosqlite.connect(DB_PATH)


# ── Jobs CRUD ──

import secrets
import string

def _nanoid(size: int = 12) -> str:
    """URL-safe nano ID (Beads 패턴)"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(size))


def _job_row(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["blocked_by"] = json.loads(d.get("blocked_by") or "[]")
    d["use_worktree"] = bool(d.get("use_worktree", 0))
    return d


async def list_jobs(status: str | None = None, time_slot: str | None = None) -> list[dict]:
    query = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if time_slot:
        query += " AND time_slot = ?"
        params.append(time_slot)
    query += " ORDER BY priority ASC, created_at ASC"

    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_job_row(r) for r in rows]


async def get_job(job_id: str) -> dict | None:
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return _job_row(row) if row else None


async def create_job(data: dict) -> dict:
    job_id = _nanoid()
    blocked_by_json = json.dumps(data.get("blocked_by", []))
    async with _get_db() as db:
        await db.execute(
            """INSERT INTO jobs
               (id, title, prompt, work_dir, priority, time_slot, scheduled_at,
                max_budget, timeout_min, model, effort, use_worktree,
                blocked_by, max_retries, jira_ticket,
                parent_job_id, resume_session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                data["title"],
                data["prompt"],
                data.get("work_dir", "~"),
                data.get("priority", 5),
                data.get("time_slot", "anytime"),
                data.get("scheduled_at"),
                data.get("max_budget", 2.0),
                data.get("timeout_min", 30),
                data.get("model", "sonnet"),
                data.get("effort", "high"),
                1 if data.get("use_worktree") else 0,
                blocked_by_json,
                data.get("max_retries", 2),
                data.get("jira_ticket"),
                data.get("parent_job_id"),
                data.get("resume_session_id"),
            ),
        )
        await db.commit()
    return await get_job(job_id)  # type: ignore


async def update_job(job_id: str, data: dict) -> dict | None:
    fields = []
    params = []
    # _UNSET: 키 자체가 없으면 skip. 명시적 None은 SQL NULL로 설정.
    # API 라우터는 exclude_none=True로 호출하므로 None이 넘어오지 않고,
    # 서비스 레이어(executor 등)에서 pid=None 같은 명시적 초기화에 사용.
    for key, value in data.items():
        if key == "blocked_by":
            fields.append("blocked_by = ?")
            params.append(json.dumps(value))
        elif key == "use_worktree":
            fields.append("use_worktree = ?")
            params.append(1 if value else 0)
        else:
            fields.append(f"{key} = ?")
            params.append(value)

    if not fields:
        return await get_job(job_id)

    params.append(job_id)
    async with _get_db() as db:
        await db.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", params
        )
        await db.commit()
    return await get_job(job_id)


async def delete_job(job_id: str) -> bool:
    async with _get_db() as db:
        cursor = await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        return cursor.rowcount > 0


# ── TimeSlots CRUD ──

def _slot_row(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 1))
    d["days"] = json.loads(d.get("days") or '["mon","tue","wed","thu","fri","sat","sun"]')
    return d


async def list_time_slots() -> list[dict]:
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM time_slots ORDER BY name")
        rows = await cursor.fetchall()
        return [_slot_row(r) for r in rows]


async def get_time_slot(name: str) -> dict | None:
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM time_slots WHERE name = ?", (name,))
        row = await cursor.fetchone()
        return _slot_row(row) if row else None


async def update_time_slot(name: str, data: dict) -> dict | None:
    fields = []
    params = []
    for key, value in data.items():
        if value is None:
            continue
        if key == "days":
            fields.append("days = ?")
            params.append(json.dumps(value))
        elif key == "enabled":
            fields.append("enabled = ?")
            params.append(1 if value else 0)
        else:
            fields.append(f"{key} = ?")
            params.append(value)

    if not fields:
        return await get_time_slot(name)

    params.append(name)
    async with _get_db() as db:
        cursor = await db.execute(
            f"UPDATE time_slots SET {', '.join(fields)} WHERE name = ?", params
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    return await get_time_slot(name)


# ── Budget CRUD ──

def _budget_row(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["remaining_usd"] = round(d["limit_usd"] - d["spent_usd"], 4)
    return d


async def get_budget(target_date: str | None = None) -> dict | None:
    if target_date is None:
        target_date = date.today().isoformat()

    # 없으면 생성
    async with _get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM budget WHERE date = ?", (target_date,))
        row = await cursor.fetchone()
        if row:
            return _budget_row(row)

        # 오늘 예산 신규 생성
        await db.execute(
            "INSERT INTO budget (date, limit_usd) VALUES (?, ?)",
            (target_date, DAILY_BUDGET_USD),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM budget WHERE date = ?", (target_date,))
        row = await cursor.fetchone()
        return _budget_row(row) if row else None


async def update_budget_limit(target_date: str, limit_usd: float) -> dict | None:
    async with _get_db() as db:
        cursor = await db.execute(
            "UPDATE budget SET limit_usd = ? WHERE date = ?", (limit_usd, target_date)
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    return await get_budget(target_date)


async def add_budget_spent(target_date: str, amount: float) -> dict | None:
    async with _get_db() as db:
        await db.execute(
            "UPDATE budget SET spent_usd = spent_usd + ?, job_count = job_count + 1 WHERE date = ?",
            (amount, target_date),
        )
        await db.commit()
    return await get_budget(target_date)

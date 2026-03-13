"""Pydantic 모델 - Job, TimeSlot, Budget"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Job ──

JobStatus = Literal["queued", "scheduled", "running", "completed", "failed", "cancelled"]
TimeSlotName = Literal["sleep", "lunch", "commute", "anytime"]
ModelName = Literal["sonnet", "opus", "haiku"]
EffortLevel = Literal["low", "medium", "high", "max"]


class JobCreate(BaseModel):
    title: str
    prompt: str
    work_dir: str = Field(default="~")
    priority: int = Field(default=5, ge=1, le=10)
    time_slot: TimeSlotName = "anytime"
    scheduled_at: str | None = None
    max_budget: float = Field(default=2.0, gt=0)
    timeout_min: int = Field(default=30, gt=0)
    model: ModelName = "sonnet"
    effort: EffortLevel = "high"
    use_worktree: bool = False
    blocked_by: list[str] = Field(default_factory=list)
    jira_ticket: str | None = None
    max_retries: int = Field(default=2, ge=0)


class JobUpdate(BaseModel):
    title: str | None = None
    prompt: str | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    time_slot: TimeSlotName | None = None
    scheduled_at: str | None = None
    max_budget: float | None = None
    status: JobStatus | None = None


class Job(BaseModel):
    id: str
    title: str
    prompt: str
    work_dir: str
    status: JobStatus
    blocked_by: list[str]
    priority: int
    time_slot: TimeSlotName
    scheduled_at: str | None
    max_budget: float
    timeout_min: int
    model: ModelName
    effort: EffortLevel
    use_worktree: bool
    session_id: str | None
    pid: int | None
    result_summary: str | None
    output_path: str | None
    error_message: str | None
    retry_count: int
    max_retries: int
    jira_ticket: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None


# ── TimeSlot ──

class TimeSlotUpdate(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    max_concurrent: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    days: list[str] | None = None


class TimeSlot(BaseModel):
    name: str
    start_time: str | None
    end_time: str | None
    max_concurrent: int
    enabled: bool
    days: list[str]


# ── Budget ──

class BudgetUpdate(BaseModel):
    limit_usd: float = Field(gt=0)


class Budget(BaseModel):
    date: str
    limit_usd: float
    spent_usd: float
    job_count: int
    remaining_usd: float


# ── Dashboard ──

class DashboardSummary(BaseModel):
    running_jobs: int
    queued_jobs: int
    today_spent_usd: float
    today_limit_usd: float
    today_job_count: int
    next_slot: str | None
    recent_completed: list[dict]
    failed_jobs: list[dict]
    # Ecosystem integration
    sentinels_pending: int = 0
    rhythm_cycle: str | None = None
    rhythm_phase: str | None = None

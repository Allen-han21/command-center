"""Dominium 생태계 통합 API"""

from __future__ import annotations

from fastapi import APIRouter

from command_center.services.integrator import (
    EcosystemSummary,
    SentinelEntry,
    get_ecosystem_summary,
    get_sentinels,
)

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


@router.get("", response_model=EcosystemSummary)
async def ecosystem_summary():
    """생태계 요약 (sentinel pending + rhythm + pr-watch)"""
    return get_ecosystem_summary()


@router.get("/sentinels", response_model=list[SentinelEntry])
async def list_sentinels(pending_only: bool = True, limit: int = 20):
    """Sentinel 파일 목록"""
    entries, _ = get_sentinels(pending_only=pending_only, limit=limit)
    return entries

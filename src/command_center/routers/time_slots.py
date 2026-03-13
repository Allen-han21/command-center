"""TimeSlot CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from command_center import db
from command_center.models import TimeSlot, TimeSlotUpdate

router = APIRouter(prefix="/api/time-slots", tags=["time-slots"])


@router.get("", response_model=list[TimeSlot])
async def list_time_slots():
    return await db.list_time_slots()


@router.get("/{name}", response_model=TimeSlot)
async def get_time_slot(name: str):
    slot = await db.get_time_slot(name)
    if not slot:
        raise HTTPException(status_code=404, detail="TimeSlot not found")
    return slot


@router.patch("/{name}", response_model=TimeSlot)
async def update_time_slot(name: str, body: TimeSlotUpdate):
    slot = await db.update_time_slot(name, body.model_dump(exclude_none=True))
    if not slot:
        raise HTTPException(status_code=404, detail="TimeSlot not found")
    return slot

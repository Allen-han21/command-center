"""Jobs CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from command_center import db
from command_center.models import Job, JobCreate, JobUpdate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[Job])
async def list_jobs(status: str | None = None, time_slot: str | None = None):
    return await db.list_jobs(status=status, time_slot=time_slot)


@router.post("", response_model=Job, status_code=201)
async def create_job(body: JobCreate):
    return await db.create_job(body.model_dump())


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=Job)
async def update_job(job_id: str, body: JobUpdate):
    job = await db.update_job(job_id, body.model_dump(exclude_none=True))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):
    deleted = await db.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/{job_id}/cancel", response_model=Job)
async def cancel_job(job_id: str):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("queued", "scheduled"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status '{job['status']}'")
    updated = await db.update_job(job_id, {"status": "cancelled"})
    return updated


@router.post("/{job_id}/retry", response_model=Job)
async def retry_job(job_id: str):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot retry job in status '{job['status']}'")
    if job["retry_count"] >= job["max_retries"]:
        raise HTTPException(status_code=400, detail="Max retries reached")
    updated = await db.update_job(job_id, {
        "status": "queued",
        "retry_count": job["retry_count"] + 1,
        "error_message": None,
        "pid": None,
        "started_at": None,
        "completed_at": None,
    })
    return updated

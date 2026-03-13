"""Level 4: FastAPI endpoint tests using httpx AsyncClient."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from command_center import db
from command_center.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
class TestJobEndpoints:
    async def test_list_empty(self, init_test_db, client):
        r = await client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_job(self, init_test_db, client):
        r = await client.post("/api/jobs", json={
            "title": "API Test",
            "prompt": "/tech-news",
            "time_slot": "lunch",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "API Test"
        assert data["status"] == "queued"
        assert data["time_slot"] == "lunch"

    async def test_get_job(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "G", "prompt": "x"})
        job_id = cr.json()["id"]
        r = await client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        assert r.json()["id"] == job_id

    async def test_get_nonexistent(self, init_test_db, client):
        r = await client.get("/api/jobs/nonexistent")
        assert r.status_code == 404

    async def test_cancel_queued_job(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "C", "prompt": "x"})
        job_id = cr.json()["id"]
        r = await client.post(f"/api/jobs/{job_id}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    async def test_cancel_running_fails(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "R", "prompt": "x"})
        job_id = cr.json()["id"]
        await db.update_job(job_id, {"status": "running"})
        r = await client.post(f"/api/jobs/{job_id}/cancel")
        assert r.status_code == 400

    async def test_retry_failed_job(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "F", "prompt": "x"})
        job_id = cr.json()["id"]
        await db.update_job(job_id, {"status": "failed", "error_message": "err"})
        r = await client.post(f"/api/jobs/{job_id}/retry")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "queued"
        assert data["retry_count"] == 1

    async def test_retry_max_reached(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "F", "prompt": "x", "max_retries": 1})
        job_id = cr.json()["id"]
        await db.update_job(job_id, {"status": "failed", "retry_count": 1})
        r = await client.post(f"/api/jobs/{job_id}/retry")
        assert r.status_code == 400
        assert "Max retries" in r.json()["detail"]

    async def test_delete_job(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "D", "prompt": "x"})
        job_id = cr.json()["id"]
        r = await client.delete(f"/api/jobs/{job_id}")
        assert r.status_code == 204

    async def test_patch_job(self, init_test_db, client):
        cr = await client.post("/api/jobs", json={"title": "Old", "prompt": "x"})
        job_id = cr.json()["id"]
        r = await client.patch(f"/api/jobs/{job_id}", json={"title": "New"})
        assert r.status_code == 200
        assert r.json()["title"] == "New"


@pytest.mark.asyncio
class TestDashboardEndpoint:
    async def test_empty_dashboard(self, init_test_db, client):
        r = await client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["running_jobs"] == 0
        assert data["queued_jobs"] == 0
        assert data["today_spent_usd"] == 0.0

    async def test_dashboard_counts(self, init_test_db, client):
        await client.post("/api/jobs", json={"title": "A", "prompt": "x"})
        await client.post("/api/jobs", json={"title": "B", "prompt": "x"})

        r = await client.get("/api/dashboard")
        assert r.json()["queued_jobs"] == 2


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health(self, init_test_db, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["name"] == "command-center"

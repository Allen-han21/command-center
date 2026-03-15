"""UC: Job Detail + Output + Continue 기능 통합 테스트.

UC1: Output endpoint — 빈 output, JSONL 파싱, limit 파라미터
UC2: parent_job_id + resume_session_id — DB 저장/조회
UC3: _build_cmd --resume 분기
UC4: Continue Job 체인 — parent→child 생성, blocked_by 설정
UC5: Output 파싱 정확성 — _summarize_event 각 타입별
"""

from __future__ import annotations

import json
import textwrap

import pytest
from httpx import ASGITransport, AsyncClient

from command_center import db
from command_center.main import app
from command_center.services.executor import _build_cmd
from command_center.routers.sessions import _summarize_event


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ── UC1: Output endpoint ──


@pytest.mark.asyncio
class TestUC1_OutputEndpoint:
    async def test_output_no_file(self, init_test_db, client):
        """output_path가 없으면 빈 결과 반환"""
        r = await client.post("/api/jobs", json={"title": "T", "prompt": "p"})
        job_id = r.json()["id"]
        r = await client.get(f"/api/jobs/{job_id}/output")
        assert r.status_code == 200
        data = r.json()
        assert data["lines"] == []
        assert data["total"] == 0

    async def test_output_nonexistent_job(self, init_test_db, client):
        """존재하지 않는 Job은 404"""
        r = await client.get("/api/jobs/nonexistent/output")
        assert r.status_code == 404

    async def test_output_parses_jsonl(self, init_test_db, client, tmp_path):
        """JSONL 파일을 파싱하여 구조화된 라인 반환"""
        r = await client.post("/api/jobs", json={"title": "T", "prompt": "p"})
        job_id = r.json()["id"]

        # JSONL 파일 생성
        output_file = tmp_path / f"{job_id}.jsonl"
        lines = [
            json.dumps({"type": "system", "subtype": "init", "session_id": "abc"}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}}),
            json.dumps({"type": "result", "result": "Done"}),
        ]
        output_file.write_text("\n".join(lines))
        await db.update_job(job_id, {"output_path": str(output_file)})

        r = await client.get(f"/api/jobs/{job_id}/output")
        data = r.json()
        assert data["total"] == 3
        assert len(data["lines"]) == 3
        assert data["lines"][0]["type"] == "system"
        assert data["lines"][1]["type"] == "assistant"
        assert data["lines"][1]["text"] == "Hello"
        assert data["lines"][2]["type"] == "result"
        assert data["lines"][2]["text"] == "Done"

    async def test_output_limit(self, init_test_db, client, tmp_path):
        """limit 파라미터로 최근 N줄만 반환"""
        r = await client.post("/api/jobs", json={"title": "T", "prompt": "p"})
        job_id = r.json()["id"]

        output_file = tmp_path / f"{job_id}.jsonl"
        lines = [json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": f"Line {i}"}]}})
                 for i in range(10)]
        output_file.write_text("\n".join(lines))
        await db.update_job(job_id, {"output_path": str(output_file)})

        r = await client.get(f"/api/jobs/{job_id}/output?limit=3")
        data = r.json()
        assert data["total"] == 10
        assert len(data["lines"]) == 3
        # 마지막 3줄이 반환됨
        assert data["lines"][0]["text"] == "Line 7"
        assert data["lines"][2]["text"] == "Line 9"

    async def test_output_malformed_json(self, init_test_db, client, tmp_path):
        """비정상 JSON은 raw 타입으로 처리"""
        r = await client.post("/api/jobs", json={"title": "T", "prompt": "p"})
        job_id = r.json()["id"]

        output_file = tmp_path / f"{job_id}.jsonl"
        output_file.write_text("not json\n{broken\n")
        await db.update_job(job_id, {"output_path": str(output_file)})

        r = await client.get(f"/api/jobs/{job_id}/output")
        data = r.json()
        assert data["total"] == 2
        assert all(l["type"] == "raw" for l in data["lines"])


# ── UC2: parent_job_id + resume_session_id DB 저장 ──


@pytest.mark.asyncio
class TestUC2_ParentAndResume:
    async def test_create_with_parent(self, init_test_db, client):
        """parent_job_id와 resume_session_id가 저장/조회되는지"""
        parent = await client.post("/api/jobs", json={"title": "Parent", "prompt": "p"})
        parent_id = parent.json()["id"]

        child = await client.post("/api/jobs", json={
            "title": "Child",
            "prompt": "follow up",
            "parent_job_id": parent_id,
            "resume_session_id": "session-uuid-123",
            "blocked_by": [parent_id],
        })
        assert child.status_code == 201
        data = child.json()
        assert data["parent_job_id"] == parent_id
        assert data["resume_session_id"] == "session-uuid-123"
        assert parent_id in data["blocked_by"]

    async def test_create_without_parent(self, init_test_db, client):
        """parent 없이 생성하면 null"""
        r = await client.post("/api/jobs", json={"title": "Solo", "prompt": "p"})
        data = r.json()
        assert data["parent_job_id"] is None
        assert data["resume_session_id"] is None

    async def test_get_preserves_fields(self, init_test_db, client):
        """GET /api/jobs/{id}에서도 새 필드가 정상 반환"""
        parent = await client.post("/api/jobs", json={"title": "P", "prompt": "p"})
        pid = parent.json()["id"]
        child = await client.post("/api/jobs", json={
            "title": "C", "prompt": "q",
            "parent_job_id": pid,
            "resume_session_id": "sess-abc",
        })
        cid = child.json()["id"]
        r = await client.get(f"/api/jobs/{cid}")
        assert r.json()["parent_job_id"] == pid
        assert r.json()["resume_session_id"] == "sess-abc"


# ── UC3: _build_cmd --resume 분기 ──


class TestUC3_BuildCmdResume:
    def test_normal_mode(self):
        """resume 없으면 --session-id 사용"""
        job = {"prompt": "hello", "model": "sonnet", "effort": "high", "max_budget": 2.0}
        cmd = _build_cmd(job, "sess-123")
        assert "--session-id" in cmd
        assert cmd[cmd.index("--session-id") + 1] == "sess-123"
        assert "--resume" not in cmd

    def test_resume_mode(self):
        """resume_session_id가 있으면 --resume 사용"""
        job = {"prompt": "follow up", "model": "sonnet", "effort": "high", "max_budget": 2.0}
        cmd = _build_cmd(job, "new-sess", resume_session_id="old-sess")
        assert "--resume" in cmd
        assert cmd[cmd.index("--resume") + 1] == "old-sess"
        assert "--session-id" not in cmd
        assert cmd[cmd.index("-p") + 1] == "follow up"

    def test_resume_with_worktree(self):
        """resume + worktree 조합"""
        job = {"prompt": "test", "model": "opus", "effort": "max", "max_budget": 5.0, "use_worktree": True}
        cmd = _build_cmd(job, "new", resume_session_id="old")
        assert "--resume" in cmd
        assert "--worktree" in cmd

    def test_resume_none_uses_session_id(self):
        """resume_session_id=None이면 --session-id"""
        job = {"prompt": "test", "model": "sonnet", "effort": "high", "max_budget": 2.0}
        cmd = _build_cmd(job, "sess-xyz", resume_session_id=None)
        assert "--session-id" in cmd
        assert "--resume" not in cmd


# ── UC4: Continue Job 체인 ──


@pytest.mark.asyncio
class TestUC4_ContinueChain:
    async def test_full_chain(self, init_test_db, client):
        """Parent 생성 → 완료 → Child 생성 (Continue) → 관계 확인"""
        # 1. Parent 생성 + 완료 시뮬레이션
        parent = await client.post("/api/jobs", json={
            "title": "Analyze PK-34080",
            "prompt": "/ai-dev.analyze PK-34080",
            "time_slot": "sleep",
            "model": "sonnet",
        })
        pid = parent.json()["id"]
        await db.update_job(pid, {
            "status": "completed",
            "session_id": "parent-session-uuid",
            "result_summary": "분석 완료: 출석 상태 8→6종 변환 필요",
            "completed_at": "2026-03-15T08:00:00Z",
        })

        # 2. Child 생성 (Resume 모드 — Continue from Job)
        child = await client.post("/api/jobs", json={
            "title": "Continue: Analyze PK-34080",
            "prompt": "spec 작성해줘",
            "parent_job_id": pid,
            "resume_session_id": "parent-session-uuid",
            "blocked_by": [pid],
            "time_slot": "sleep",
        })
        assert child.status_code == 201
        cdata = child.json()
        assert cdata["parent_job_id"] == pid
        assert cdata["resume_session_id"] == "parent-session-uuid"
        assert pid in cdata["blocked_by"]

        # 3. Parent 조회 — 여전히 정상
        r = await client.get(f"/api/jobs/{pid}")
        assert r.json()["status"] == "completed"
        assert r.json()["result_summary"] == "분석 완료: 출석 상태 8→6종 변환 필요"

    async def test_new_job_mode(self, init_test_db, client):
        """New Job 모드: resume_session_id 없이 parent_job_id만"""
        parent = await client.post("/api/jobs", json={"title": "P", "prompt": "p"})
        pid = parent.json()["id"]
        await db.update_job(pid, {"status": "completed", "result_summary": "Done"})

        child = await client.post("/api/jobs", json={
            "title": "Continue: P",
            "prompt": "[이전 작업: P]\nDone\n\n---\n\n추가 작업 요청",
            "parent_job_id": pid,
            "blocked_by": [pid],
        })
        cdata = child.json()
        assert cdata["parent_job_id"] == pid
        assert cdata["resume_session_id"] is None
        assert "[이전 작업: P]" in cdata["prompt"]


# ── UC5: _summarize_event 각 타입별 ──


class TestUC5_SummarizeEvent:
    def test_assistant_text(self):
        event = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello world"}]}}
        result = _summarize_event(event)
        assert result["type"] == "assistant"
        assert result["text"] == "Hello world"

    def test_assistant_tool_use(self):
        event = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}
        result = _summarize_event(event)
        assert result["type"] == "assistant"
        assert "[tool: Bash]" in result["text"]

    def test_assistant_mixed(self):
        event = {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Let me check"},
            {"type": "tool_use", "name": "Read"},
        ]}}
        result = _summarize_event(event)
        assert "Let me check" in result["text"]
        assert "[tool: Read]" in result["text"]

    def test_assistant_empty_content(self):
        event = {"type": "assistant", "message": {"content": []}}
        result = _summarize_event(event)
        assert result["text"] == "..."

    def test_tool_use(self):
        event = {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}
        result = _summarize_event(event)
        assert result["type"] == "tool_use"
        assert "Bash" in result["text"]
        assert "ls -la" in result["text"]

    def test_tool_result(self):
        event = {"type": "tool_result", "content": "file1.py\nfile2.py"}
        result = _summarize_event(event)
        assert result["type"] == "tool_result"
        assert "file1.py" in result["text"]

    def test_result(self):
        event = {"type": "result", "result": "Task completed"}
        result = _summarize_event(event)
        assert result["type"] == "result"
        assert result["text"] == "Task completed"

    def test_result_truncated(self):
        event = {"type": "result", "result": "x" * 500}
        result = _summarize_event(event)
        assert len(result["text"]) == 300

    def test_unknown_type(self):
        event = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}}
        result = _summarize_event(event)
        assert result["type"] == "rate_limit_event"

    def test_system_init(self):
        event = {"type": "system", "subtype": "init", "session_id": "abc", "cwd": "/Users/allen"}
        result = _summarize_event(event)
        assert result["type"] == "system"
        assert "session_id" in result["text"]

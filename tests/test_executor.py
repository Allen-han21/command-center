"""Level 1: Pure function tests for executor."""

from __future__ import annotations

import json

from command_center.services.executor import _build_cmd, _extract_result_summary


class TestBuildCmd:
    def test_default_job(self):
        job = {"prompt": "hello", "model": "sonnet", "effort": "high", "max_budget": 2.0}
        cmd = _build_cmd(job, "sess-123")
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert cmd[cmd.index("--model") + 1] == "claude-sonnet-4-6"
        assert cmd[cmd.index("--session-id") + 1] == "sess-123"
        assert cmd[cmd.index("--max-budget-usd") + 1] == "2.0"
        assert cmd[cmd.index("-p") + 1] == "hello"
        assert "--worktree" not in cmd

    def test_opus_model(self):
        job = {"prompt": "test", "model": "opus", "effort": "max", "max_budget": 5.0}
        cmd = _build_cmd(job, "s1")
        assert cmd[cmd.index("--model") + 1] == "claude-opus-4-6"
        assert cmd[cmd.index("--effort") + 1] == "max"

    def test_haiku_model(self):
        job = {"prompt": "test", "model": "haiku", "effort": "low", "max_budget": 0.5}
        cmd = _build_cmd(job, "s1")
        assert cmd[cmd.index("--model") + 1] == "claude-haiku-4-5-20251001"

    def test_worktree_flag(self):
        job = {"prompt": "test", "model": "sonnet", "effort": "high", "max_budget": 2.0, "use_worktree": True}
        cmd = _build_cmd(job, "s1")
        assert "--worktree" in cmd

    def test_unknown_model_fallback(self):
        """알 수 없는 모델명은 sonnet으로 fallback."""
        job = {"prompt": "test", "model": "unknown", "effort": "high", "max_budget": 2.0}
        cmd = _build_cmd(job, "s1")
        assert cmd[cmd.index("--model") + 1] == "claude-sonnet-4-6"


class TestExtractResultSummary:
    def test_valid_result(self):
        lines = [
            json.dumps({"type": "assistant", "content": "thinking..."}),
            json.dumps({"type": "result", "result": "Task completed successfully"}),
        ]
        stdout = "\n".join(lines).encode()
        assert _extract_result_summary(stdout) == "Task completed successfully"

    def test_no_result_type(self):
        lines = [json.dumps({"type": "assistant", "content": "hello"})]
        stdout = "\n".join(lines).encode()
        assert _extract_result_summary(stdout) == ""

    def test_empty_bytes(self):
        assert _extract_result_summary(b"") == ""

    def test_malformed_json(self):
        """비정상 JSON은 무시하고 빈 문자열 반환."""
        stdout = b"not json\n{broken\n"
        assert _extract_result_summary(stdout) == ""

    def test_result_truncated_at_500(self):
        long_result = "x" * 1000
        lines = [json.dumps({"type": "result", "result": long_result})]
        stdout = "\n".join(lines).encode()
        summary = _extract_result_summary(stdout)
        assert len(summary) == 500

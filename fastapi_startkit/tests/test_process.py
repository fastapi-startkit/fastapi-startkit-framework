import json

import pytest

from fastapi_startkit.process import Process


class TestProcess:
    def test_run_captures_stdout(self):
        result = Process.run("echo hello")
        assert result.output().strip() == "hello"
        assert result.exit_code() == 0
        assert result.successful()

    def test_run_captures_stderr(self):
        result = Process.run("ls /nonexistent_path_xyz 2>&1 || true")
        assert result.exit_code() == 0  # we used || true

    def test_run_exit_code_on_failure(self):
        result = Process.run("exit 42", timeout=5)
        assert result.exit_code() == 42
        assert not result.successful()

    def test_run_captures_stderr_separately(self):
        result = Process.run("echo error_message >&2; exit 1")
        assert result.exit_code() == 1
        assert "error_message" in result.error()
        assert not result.successful()

    def test_run_output_json(self):
        payload = json.dumps({"key": "value", "number": 42})
        result = Process.run(f"echo '{payload}'")
        data = result.output_json()
        assert data["key"] == "value"
        assert data["number"] == 42

    @pytest.mark.asyncio
    async def test_run_async_captures_stdout(self):
        result = await Process.run_async("echo async_hello")
        assert result.output().strip() == "async_hello"
        assert result.exit_code() == 0

    @pytest.mark.asyncio
    async def test_run_async_exit_code(self):
        result = await Process.run_async("exit 1")
        assert result.exit_code() == 1
        assert not result.successful()

    @pytest.mark.asyncio
    async def test_run_async_output_json(self):
        payload = json.dumps({"status": "ok", "items": [1, 2, 3]})
        result = await Process.run_async(f"echo '{payload}'")
        data = result.output_json()
        assert data["status"] == "ok"
        assert data["items"] == [1, 2, 3]

    def test_repr(self):
        result = Process.run("echo repr_test")
        r = repr(result)
        assert "ProcessResult" in r
        assert "exit_code=0" in r

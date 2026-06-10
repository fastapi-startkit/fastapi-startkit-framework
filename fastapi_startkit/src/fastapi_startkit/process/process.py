from __future__ import annotations

import asyncio
import subprocess


class ProcessResult:
    def __init__(self, stdout: str, stderr: str, returncode: int) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode

    def output(self) -> str:
        return self._stdout

    def exit_code(self) -> int:
        return self._returncode

    def error(self) -> str:
        return self._stderr

    def successful(self) -> bool:
        return self._returncode == 0

    def output_json(self) -> dict | list:
        import json

        return json.loads(self._stdout)

    def __repr__(self) -> str:
        return f"ProcessResult(exit_code={self._returncode}, output={self._stdout[:80]!r})"


class Process:
    @staticmethod
    def run(
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout: float | None = None,
    ) -> ProcessResult:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
        return ProcessResult(result.stdout, result.stderr, result.returncode)

    @staticmethod
    async def run_async(
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout: float | None = None,
    ) -> ProcessResult:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise
        return ProcessResult(
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
            proc.returncode or 0,
        )

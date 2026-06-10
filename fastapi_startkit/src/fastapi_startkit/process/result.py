from __future__ import annotations

import json
from typing import Any

from .exception import ProcessFailedException, ProcessJsonDecodeError


class ProcessResult:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
        args: str = "",
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self._returncode = returncode
        self._args = args

    def command(self) -> str:
        return self._args

    def successful(self) -> bool:
        return self._returncode == 0

    def failed(self) -> bool:
        return self._returncode != 0

    def output(self) -> str:
        return self._stdout or ""

    def error_output(self) -> str:
        return self._stderr or ""

    def error(self) -> str:
        """Alias for error_output() — stderr as a string."""
        return self.error_output()

    def exit_code(self) -> int:
        return self._returncode

    def output_json(self) -> Any:
        """Parse stdout as JSON.

        Raises ProcessJsonDecodeError if stdout is not valid JSON.
        """
        try:
            return json.loads(self._stdout)
        except json.JSONDecodeError as exc:
            raise ProcessJsonDecodeError(self._stdout, exc) from exc

    def throw(self) -> "ProcessResult":
        """Raise ProcessFailedException if the process failed."""
        if self.failed():
            raise ProcessFailedException(self)
        return self

    def throw_if(self, condition: Any) -> "ProcessResult":
        """Raise ProcessFailedException if condition is truthy."""
        if condition:
            self.throw()
        return self

    def __repr__(self) -> str:
        return f"ProcessResult(exit_code={self._returncode},output={self._stdout!r})"

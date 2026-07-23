from .result import ProcessResult


class FakeProcessDescription:
    def __init__(self) -> None:
        self._output_sequences: list[tuple[str, str]] = []
        self._exit_code: int = 0

    def output(self, text: str) -> "FakeProcessDescription":
        """Add a stdout line to the fake output."""
        self._output_sequences.append(("stdout", text))
        return self

    def error_output(self, text: str) -> "FakeProcessDescription":
        """Add a stderr line to the fake output."""
        self._output_sequences.append(("stderr", text))
        return self

    def exit_code(self, code: int) -> "FakeProcessDescription":
        self._exit_code = code
        return self

    def to_result(self, command: str) -> "ProcessResult":
        stdout_lines = [t for kind, t in self._output_sequences if kind == "stdout"]
        stderr_lines = [t for kind, t in self._output_sequences if kind == "stderr"]
        return ProcessResult(
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            returncode=self._exit_code,
            args=command,
        )

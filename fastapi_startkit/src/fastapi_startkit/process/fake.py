from .result import ProcessResult


class FakeProcessDescription:
    def __init__(self):
        self._output_sequences = []
        self._exit_code = 0
        self._iterations = 1

    def output(self, text: str):
        """Add a stdout line to the fake output."""
        self._output_sequences.append(('stdout', text))
        return self

    def error_output(self, text: str):
        """Add a stderr line to the fake output."""
        self._output_sequences.append(('stderr', text))
        return self

    def exit_code(self, code: int):
        self._exit_code = code
        return self

    def iterations(self, count: int):
        """How many times this fake can be matched before cycling."""
        self._iterations = count
        return self

    def to_result(self, command: str) -> 'ProcessResult':
        stdout_lines = [t for kind, t in self._output_sequences if kind == 'stdout']
        stderr_lines = [t for kind, t in self._output_sequences if kind == 'stderr']

        class _FakeCompleted:
            pass

        cp = _FakeCompleted()
        cp.args = command
        cp.stdout = '\n'.join(stdout_lines)
        cp.stderr = '\n'.join(stderr_lines)
        cp.returncode = self._exit_code
        return ProcessResult(cp)

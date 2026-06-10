class ProcessFailedException(Exception):
    def __init__(self, result):
        self.result = result
        super().__init__(
            f"Process [{result.command()}] failed with exit code {result.exit_code()}.\n{result.error_output()}"
        )


class ProcessTimedOutException(Exception):
    def __init__(self, command):
        self.command = command
        super().__init__(f"Process [{command}] timed out.")


class ProcessJsonDecodeError(ValueError):
    def __init__(self, stdout: str, original: Exception) -> None:
        self.stdout = stdout
        self.original = original
        super().__init__(
            f"Failed to parse process output as JSON: {original}\nRaw output: {stdout!r}"
        )

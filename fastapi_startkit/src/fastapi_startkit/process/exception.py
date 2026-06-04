
class ProcessFailedException(Exception):
    def __init__(self, result):
        self.result = result
        super().__init__(
            f"Process [{result.command()}] failed with exit code {result.exit_code()}.\n"
            f"{result.error_output()}"
        )


class ProcessTimedOutException(Exception):
    def __init__(self, command):
        self.command = command
        super().__init__(f"Process [{command}] timed out.")


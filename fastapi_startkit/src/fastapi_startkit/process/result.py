from .exception import ProcessFailedException


class ProcessResult:
    def __init__(self, completed_process):
        self._process = completed_process

    def command(self):
        return self._process.args

    def successful(self):
        return self._process.returncode == 0

    def failed(self):
        return self._process.returncode != 0

    def output(self):
        return self._process.stdout or ''

    def error_output(self):
        return self._process.stderr or ''

    def exit_code(self):
        return self._process.returncode

    def throw(self):
        """Raise ProcessFailedException if the process failed."""
        if self.failed():
            raise ProcessFailedException(self)
        return self

    def throw_if(self, condition):
        """Raise ProcessFailedException if condition is truthy."""
        if condition:
            self.throw()
        return self

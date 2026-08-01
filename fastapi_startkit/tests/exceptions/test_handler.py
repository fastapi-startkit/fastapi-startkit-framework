"""The global exception handler must log the full stack trace, not just the
exception message, so failures are actionable in production logs (task #1347)."""

import contextlib
import io
from unittest import mock

from fastapi_startkit.exceptions.handler import ExceptionHandler


class _FakeApp:
    """Minimal stand-in for the Application used by ExceptionHandler.report()."""

    def __init__(self, *, debug: bool = False, has_logger: bool = True) -> None:
        self._debug = debug
        self._has_logger = has_logger

    def has(self, key: str) -> bool:
        return self._has_logger and key == "logger"

    def is_debug(self) -> bool:
        return self._debug


def _raise(message: str) -> Exception:
    """Return a caught exception carrying a real traceback."""
    try:
        raise ModuleNotFoundError(message)
    except ModuleNotFoundError as exc:
        return exc


class TestExceptionHandlerLogsTraceback:
    def test_logs_full_traceback_even_when_not_in_debug(self):
        handler = ExceptionHandler(_FakeApp(debug=False))
        exc = _raise("No module named 'app.agents.chat'")

        with mock.patch("fastapi_startkit.logging.logger.Logger.error") as log:
            handler.report(exc)

        log.assert_called_once()
        logged = log.call_args.args[0]
        assert "Traceback (most recent call last):" in logged
        assert "ModuleNotFoundError: No module named 'app.agents.chat'" in logged
        assert "test_handler.py" in logged  # the frame where it was raised

    def test_logs_full_traceback_in_debug_too(self):
        handler = ExceptionHandler(_FakeApp(debug=True))
        exc = _raise("boom")

        with mock.patch("fastapi_startkit.logging.logger.Logger.error") as log:
            handler.report(exc)

        assert "Traceback (most recent call last):" in log.call_args.args[0]

    def test_prints_full_traceback_to_stderr_when_no_logger(self):
        handler = ExceptionHandler(_FakeApp(has_logger=False))
        exc = _raise("no logger here")

        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            handler.report(exc)

        printed = buffer.getvalue()
        assert "Traceback (most recent call last):" in printed
        assert "ModuleNotFoundError: no logger here" in printed

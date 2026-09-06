"""Tests for the core ``ExceptionHandler`` (task #722).

Exercises registration, report/render dispatch, the reporting fallbacks
(custom reporter, handler.report, logger, stderr), context building, and the
excepthook/install wiring. The application, logger, and ``atexit`` are all
faked/patched so nothing global is left mutated.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi_startkit.exceptions.handler import ExceptionHandler


class CustomError(Exception):
    pass


class ChildError(CustomError):
    pass


def _app(*, has_logger=False, debug=False):
    return SimpleNamespace(
        has=lambda name: has_logger and name == "logger",
        is_debug=lambda: debug,
    )


class TestRegistration:
    def test_register_is_noop(self):
        assert ExceptionHandler().register() is None

    def test_dont_report_controls_should_report(self):
        handler = ExceptionHandler()
        assert handler.dont_report([CustomError]) is handler
        assert handler.should_report(CustomError("x")) is False
        assert handler.should_report(ValueError("x")) is True

    def test_resolve_handler_uses_mro(self):
        handler = ExceptionHandler()
        registered = MagicMock()
        handler.register_handler(CustomError, registered)
        # A subclass instance resolves to the parent's registered handler.
        assert handler._resolve_handler(ChildError("x")) is registered
        assert handler._resolve_handler(KeyError("x")) is None


class TestReport:
    def test_skips_when_should_not_report(self):
        handler = ExceptionHandler().dont_report([CustomError])
        with patch.object(handler, "report_exception") as report_exception:
            handler.report(CustomError("x"))
        report_exception.assert_not_called()

    def test_custom_reporter_takes_priority(self):
        handler = ExceptionHandler()
        reporter = MagicMock()
        handler.register_report(CustomError, reporter)
        exc = CustomError("boom")
        handler.report(exc)
        reporter.assert_called_once_with(exc)

    def test_handler_report_used_when_present(self):
        handler = ExceptionHandler()
        registered = MagicMock()
        handler.register_handler(CustomError, registered)
        exc = CustomError("boom")
        handler.report(exc)
        registered.report.assert_called_once_with(exc)

    def test_falls_back_to_report_exception(self):
        handler = ExceptionHandler()
        with patch.object(handler, "report_exception") as report_exception:
            exc = ValueError("boom")
            handler.report(exc)
        report_exception.assert_called_once_with(exc)


class TestReportException:
    def test_uses_logger_when_available(self):
        handler = ExceptionHandler(_app(has_logger=True))
        with patch("fastapi_startkit.logging.logger.Logger.error") as error:
            handler.report_exception(ValueError("boom"))
        error.assert_called_once()
        assert "boom" in error.call_args.args[0]

    def test_prints_to_stderr_without_logger(self, capsys):
        handler = ExceptionHandler()  # no app
        handler.report_exception(ValueError("boom"))
        assert "boom" in capsys.readouterr().err

    def test_build_context_plain_without_debug(self):
        handler = ExceptionHandler(_app(debug=False))
        assert handler._build_context(ValueError("boom")) == "ValueError: boom"

    def test_build_context_includes_traceback_in_debug(self):
        handler = ExceptionHandler(_app(debug=True))
        try:
            raise ValueError("boom")
        except ValueError as exc:
            context = handler._build_context(exc)
        assert context.startswith("ValueError: boom")
        assert "Traceback" in context


class TestRenderAndHandle:
    async def test_render_uses_custom_callable(self):
        handler = ExceptionHandler()
        handler.register_render(CustomError, lambda request, exc: ("rendered", request, exc))
        exc = CustomError("boom")
        result = await handler.render(exc, {"request": "req"})
        assert result == ("rendered", "req", exc)

    async def test_render_uses_handler_render(self):
        handler = ExceptionHandler()

        class Registered:
            async def render(self, request, exc):
                return ("handled", request, exc)

        handler.register_handler(CustomError, Registered())
        exc = CustomError("boom")
        assert await handler.render(exc, {"request": "req"}) == ("handled", "req", exc)

    async def test_render_returns_none_by_default(self):
        assert await ExceptionHandler().render(ValueError("x"), {}) is None

    async def test_handle_reports_then_renders(self):
        handler = ExceptionHandler()
        handler.register_render(CustomError, lambda request, exc: "done")
        with patch.object(handler, "report") as report:
            result = await handler.handle(CustomError("boom"), {"request": None})
        report.assert_called_once()
        assert result == "done"

    async def test_handle_defaults_context_to_empty_dict(self):
        handler = ExceptionHandler()
        with patch.object(handler, "report"):
            assert await handler.handle(ValueError("boom")) is None


class TestExcepthookAndInstall:
    def test_excepthook_delegates_keyboard_interrupt(self):
        handler = ExceptionHandler()
        with patch("sys.__excepthook__") as default_hook, patch.object(handler, "report") as report:
            handler._excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        default_hook.assert_called_once()
        report.assert_not_called()

    def test_excepthook_reports_other_exceptions(self):
        handler = ExceptionHandler()
        exc = ValueError("boom")
        with patch.object(handler, "report") as report:
            handler._excepthook(ValueError, exc, None)
        report.assert_called_once_with(exc)

    def test_handle_shutdown_is_noop(self):
        assert ExceptionHandler().handle_shutdown() is None

    def test_install_wires_excepthook_and_atexit(self):
        handler = ExceptionHandler()
        original = sys.excepthook
        try:
            with patch("atexit.register") as register:
                assert handler.install() is handler
            assert sys.excepthook == handler._excepthook
            register.assert_called_once_with(handler.handle_shutdown)
        finally:
            sys.excepthook = original

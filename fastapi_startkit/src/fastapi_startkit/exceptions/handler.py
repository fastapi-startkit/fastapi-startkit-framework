import sys
import atexit
from typing import Any, Callable, Dict, List, Optional, Type


class ExceptionHandler:
    def __init__(self, application=None):
        self.app = application
        self._handlers: Dict[Type[Exception], Any] = {}
        self._renders: Dict[Type[Exception], Callable] = {}
        self._reports: Dict[Type[Exception], Callable] = {}
        self._dont_report: List[Type[Exception]] = []

    def register(self):
        """Override in subclasses to register handlers, renders, and report rules."""
        pass

    def dont_report(self, exceptions: List[Type[Exception]]):
        self._dont_report.extend(exceptions)
        return self

    def register_handler(self, exc_class: Type[Exception], handler):
        """Register a handler instance for an exception type.

        The handler must implement report(exc) and/or render(request, exc).
        """
        self._handlers[exc_class] = handler
        return self

    def register_render(self, exc_class: Type[Exception], callable: Callable):
        """Register a render callable: (request, exc) -> Response."""
        self._renders[exc_class] = callable
        return self

    def register_report(self, exc_class: Type[Exception], callable: Callable):
        """Register a report callable: (exc) -> None."""
        self._reports[exc_class] = callable
        return self

    def should_report(self, exception: Exception) -> bool:
        return not any(isinstance(exception, exc) for exc in self._dont_report)

    def report(self, exception: Exception):
        if not self.should_report(exception):
            return

        exc_type = type(exception)

        # Per-exception custom reporter takes priority
        if exc_type in self._reports:
            self._reports[exc_type](exception)
            return

        # Per-exception handler may also implement report()
        handler = self._resolve_handler(exception)
        if handler and hasattr(handler, "report"):
            handler.report(exception)
            return

        self.report_exception(exception)

    def report_exception(self, exception: Exception):
        context = self._build_context(exception)
        if self.app and self.app.has("logger"):
            from fastapi_startkit.logging.logger import Logger

            Logger.error(context)
        else:
            print(context, file=sys.stderr)

    def _build_context(self, exception: Exception) -> str:
        import traceback

        context = f"{type(exception).__name__}: {exception}"
        if self.app and self.app.is_debug():
            context += "\n" + "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        return context

    async def handle(self, exception: Exception, context: Optional[Dict] = None) -> Any:
        """Main entry point called from the FastAPI exception_handler hook."""
        self.report(exception)
        return await self.render(exception, context or {})

    async def render(self, exception: Exception, context: Dict) -> Any:
        request = context.get("request")
        exc_type = type(exception)

        # Per-exception custom render callable: (request, exc) -> Response
        if exc_type in self._renders:
            return self._renders[exc_type](request, exception)

        # Per-exception handler may implement render()
        handler = self._resolve_handler(exception)
        if handler and hasattr(handler, "render"):
            return await handler.render(request, exception)

        return None  # caller falls back to its own default

    def _resolve_handler(self, exception: Exception) -> Optional[Any]:
        """Find the most specific registered handler for an exception."""
        for exc_class in type(exception).__mro__:
            if exc_class in self._handlers:
                return self._handlers[exc_class]
        return None

    def _excepthook(self, exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        self.report(exc_value)

    def handle_shutdown(self):
        """Called by atexit on clean process exit. Override to flush buffers etc."""
        pass

    def install(self):
        """Wire up sys.excepthook and atexit."""
        sys.excepthook = self._excepthook
        atexit.register(self.handle_shutdown)
        return self

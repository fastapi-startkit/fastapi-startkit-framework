import io
import logging
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from fastapi_startkit.application import app as get_app
from fastapi_startkit.logging.ChannelFactory import ChannelFactory
from fastapi_startkit.logging.channels import (
    DailyChannel,
    SingleChannel,
    StackChannel,
    TerminalChannel,
)
from fastapi_startkit.logging.channels.BaseChannel import BaseChannel
from fastapi_startkit.logging.channels.MultiBaseChannel import MultiBaseChannel
from fastapi_startkit.logging.config import LoggingConfig
from fastapi_startkit.logging.config import channels as config_channels
from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver
from fastapi_startkit.logging.drivers.LogSingleDriver import LogSingleDriver
from fastapi_startkit.logging.drivers.LogSlackDriver import LogSlackDriver
from fastapi_startkit.logging.drivers.LogSyslogDriver import LogSyslogDriver
from fastapi_startkit.logging.drivers.LogTerminalDriver import LogTerminalDriver
from fastapi_startkit.logging.factory import DriverFactory
from fastapi_startkit.logging.file import make_directory
from fastapi_startkit.logging.handler import LoggingHandler
from fastapi_startkit.logging.listeners import LoggerExceptionListener
from fastapi_startkit.logging.logger import Logger
from fastapi_startkit.logging.managers import LoggingManager
from fastapi_startkit.logging.providers.log_provider import LogProvider


_root_logger_state = {}


def setUpModule():
    """Register the logging config against the booted test app so the channels
    that read `logging.*` config keys can be constructed.

    Registering constructs a LoggingManager, which installs a LoggingHandler on
    the real root logger. That handler routes every stdlib log record back through
    the app logger, so it must be torn down or it corrupts every later test module.
    """
    root = logging.getLogger()
    _root_logger_state["handlers"] = list(root.handlers)
    _root_logger_state["level"] = root.level

    app = get_app()
    try:
        _root_logger_state["logger_binding"] = app.make("logger")
    except Exception:
        _root_logger_state["logger_binding"] = None

    LogProvider(app).register()


def tearDownModule():
    """Restore the real root logger and app state mutated during this module."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if handler not in _root_logger_state.get("handlers", []):
            root.removeHandler(handler)
    root.setLevel(_root_logger_state.get("level", logging.WARNING))

    Logger.instance = None
    get_app().bind("logger", _root_logger_state.get("logger_binding"))


class RecordingDriver(BaseDriver):
    """A driver that records the level methods invoked on it."""

    def __init__(self, should_run=True):
        self._should_run = should_run
        self.calls = []

    def should_run(self, level, max_level):
        return self._should_run

    def _record(self, level):
        def method(message, *args, **kwargs):
            self.calls.append((level, message))
            return f"{level}:{message}"

        return method

    def __getattr__(self, name):
        if name in BaseDriver.levels:
            return self._record(name)
        raise AttributeError(name)


class ChannelFactoryTest(unittest.TestCase):
    def test_make_returns_registered_channel_classes(self):
        self.assertIs(ChannelFactory.make("single"), SingleChannel)
        self.assertIs(ChannelFactory.make("daily"), DailyChannel)
        self.assertIs(ChannelFactory.make("terminal"), TerminalChannel)
        self.assertIs(ChannelFactory.make("stack"), StackChannel)

    def test_make_returns_none_for_unknown_channel(self):
        self.assertIsNone(ChannelFactory.make("does-not-exist"))

    def test_register_adds_new_channels(self):
        marker = object()
        try:
            ChannelFactory.register({"custom_test_channel": marker})
            self.assertIs(ChannelFactory.make("custom_test_channel"), marker)
        finally:
            ChannelFactory.channels.pop("custom_test_channel", None)


class DriverFactoryTest(unittest.TestCase):
    def test_make_maps_names_to_driver_classes(self):
        self.assertIs(DriverFactory.make("single"), LogSingleDriver)
        self.assertIs(DriverFactory.make("daily"), LogSingleDriver)
        self.assertIs(DriverFactory.make("slack"), LogSlackDriver)
        self.assertIs(DriverFactory.make("syslog"), LogSyslogDriver)
        self.assertIs(DriverFactory.make("terminal"), LogTerminalDriver)

    def test_make_returns_none_for_unknown_driver(self):
        self.assertIsNone(DriverFactory.make("unknown"))


class BaseDriverShouldRunTest(unittest.TestCase):
    def setUp(self):
        self.driver = BaseDriver()

    def test_returns_true_when_no_max_level(self):
        self.assertTrue(self.driver.should_run("debug", None))

    def test_more_severe_level_runs_under_a_less_severe_threshold(self):
        # error (index 3) is more severe than info (index 6)
        self.assertTrue(self.driver.should_run("error", "info"))

    def test_less_severe_level_is_filtered_out(self):
        # debug (index 7) is less severe than info (index 6)
        self.assertFalse(self.driver.should_run("debug", "info"))

    def test_equal_level_runs(self):
        self.assertTrue(self.driver.should_run("info", "info"))

    def test_get_time_returns_formatted_datetime(self):
        self.assertIsInstance(self.driver.get_time().to_datetime_string(), str)


class BaseChannelTest(unittest.TestCase):
    def _channel(self, should_run=True, max_level="debug"):
        channel = BaseChannel()
        channel.driver = RecordingDriver(should_run=should_run)
        channel.max_level = max_level
        return channel

    def test_level_methods_delegate_to_driver_when_allowed(self):
        channel = self._channel(should_run=True)
        for level in ("emergency", "alert", "critical", "error", "warning", "notice", "info", "debug"):
            result = getattr(channel, level)("message")
            self.assertEqual(result, f"{level}:message")
        self.assertEqual(len(channel.driver.calls), 8)

    def test_level_methods_are_suppressed_when_not_allowed(self):
        channel = self._channel(should_run=False)
        self.assertIsNone(channel.info("message"))
        self.assertIsNone(channel.error("message"))
        self.assertEqual(channel.driver.calls, [])

    def test_log_reports_whether_level_should_run(self):
        self.assertTrue(self._channel(should_run=True).log("info", "m"))
        self.assertFalse(self._channel(should_run=False).log("info", "m"))

    def test_channel_builds_a_new_channel_instance(self):
        channel = self._channel()
        self.assertIsInstance(channel.channel("terminal"), TerminalChannel)


class MultiBaseChannelTest(unittest.TestCase):
    def _multi(self, should_run=True):
        inner = BaseChannel()
        inner.driver = RecordingDriver(should_run=should_run)
        inner.max_level = "debug"
        multi = MultiBaseChannel()
        multi.channels = [inner]
        return multi, inner

    def test_broadcasts_each_level_to_all_channels(self):
        multi, inner = self._multi(should_run=True)
        for level in ("emergency", "alert", "critical", "error", "warning", "notice", "info", "debug"):
            getattr(multi, level)("message")
        recorded = [level for level, _ in inner.driver.calls]
        self.assertEqual(
            recorded,
            ["emergency", "alert", "critical", "error", "warning", "notice", "info", "debug"],
        )

    def test_skips_channels_that_should_not_run(self):
        multi, inner = self._multi(should_run=False)
        multi.info("message")
        multi.error("message")
        self.assertEqual(inner.driver.calls, [])


class TerminalDriverTest(unittest.TestCase):
    def setUp(self):
        self.driver = LogTerminalDriver()

    def test_get_format_includes_time_level_and_message(self):
        formatted = self.driver.get_format("hello", "INFO")
        self.assertIn("INFO", formatted)
        self.assertIn("hello", formatted)
        self.assertRegex(formatted, r"\d{4}-\d{2}-\d{2}")

    def test_each_level_writes_to_stdout(self):
        for level, method in (
            ("EMERGENCY", self.driver.emergency),
            ("ALERT", self.driver.alert),
            ("CRITICAL", self.driver.critical),
            ("ERROR", self.driver.error),
            ("WARNING", self.driver.warning),
            ("NOTICE", self.driver.notice),
            ("INFO", self.driver.info),
            ("DEBUG", self.driver.debug),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                method("payload")
            output = buffer.getvalue()
            self.assertIn(level, output)
            self.assertIn("payload", output)


class SingleDriverTest(unittest.TestCase):
    def setUp(self):
        # The single/syslog drivers log through the "root"-named logger; disable
        # propagation so records do not reach the installed LoggingHandler.
        self.root_named = logging.getLogger("root")
        self._propagate = self.root_named.propagate
        self.root_named.propagate = False
        self._existing_handlers = list(self.root_named.handlers)

    def tearDown(self):
        for handler in list(self.root_named.handlers):
            if handler not in self._existing_handlers:
                self.root_named.removeHandler(handler)
                handler.close()
        self.root_named.propagate = self._propagate

    def test_writes_formatted_levels_to_the_file(self):
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        try:
            driver = LogSingleDriver(path=path, max_level="debug")
            driver.error("boom")
            driver.info("ping")
            with open(path) as handle:
                contents = handle.read()
            self.assertIn("ERROR", contents)
            self.assertIn("boom", contents)
            self.assertIn("INFO", contents)
            self.assertIn("ping", contents)
        finally:
            os.remove(path)

    def test_change_format_replaces_handlers(self):
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        try:
            driver = LogSingleDriver(path=path, max_level="debug")
            before = len(driver.log.handlers)
            driver.change_format("%(message)s")
            self.assertLessEqual(len(driver.log.handlers), before)
            self.assertTrue(len(driver.log.handlers) >= 1)
        finally:
            os.remove(path)


class SlackDriverTest(unittest.TestCase):
    def _driver(self):
        return LogSlackDriver(token="tok", channel="#bot", username="bot", emoji=":x:")

    def test_get_format_includes_level_and_message(self):
        formatted = self._driver().get_format("hi", "ERROR")
        self.assertIn("ERROR", formatted)
        self.assertIn("hi", formatted)

    def test_level_methods_post_to_slack(self):
        driver = self._driver()
        with patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock, \
                patch.object(driver, "find_channel", return_value="C123"):
            driver.error("boom")
            requests_mock.post.assert_called_once()
            args, _ = requests_mock.post.call_args
            self.assertEqual(args[0], driver.slack_url)
            self.assertIn("boom", args[1]["text"])

    def test_find_channel_resolves_channel_id(self):
        driver = self._driver()
        response = MagicMock()
        response.json.return_value = {"channels": [{"name": "bot", "id": "C123"}]}
        with patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock:
            requests_mock.post.return_value = response
            self.assertEqual(driver.find_channel("#bot"), "C123")

    def test_find_channel_raises_when_missing(self):
        driver = self._driver()
        response = MagicMock()
        response.json.return_value = {"channels": [{"name": "other", "id": "C999"}]}
        with patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock:
            requests_mock.post.return_value = response
            with self.assertRaises(Exception):
                driver.find_channel("#bot")


class SyslogDriverTest(unittest.TestCase):
    def test_levels_route_to_the_underlying_logger(self):
        with patch("fastapi_startkit.logging.drivers.LogSyslogDriver.logging.handlers.SysLogHandler"):
            driver = LogSyslogDriver(path="/dev/null")
        driver.log = MagicMock()
        driver.error("boom")
        driver.log.error.assert_called_once_with("boom")
        driver.info("ping")
        driver.log.info.assert_called_once_with("ping")
        driver.critical("halt")
        driver.log.critical.assert_called_once_with("halt")


class ChannelConstructionTest(unittest.TestCase):
    def test_terminal_channel_uses_terminal_driver(self):
        channel = TerminalChannel()
        self.assertEqual(channel.max_level, "info")
        self.assertIsInstance(channel.driver, LogTerminalDriver)

    def test_single_channel_builds_single_driver(self):
        import tempfile
        import os

        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "single.log")
        try:
            channel = SingleChannel(driver="single", path=path)
            self.assertIsInstance(channel.driver, LogSingleDriver)
        finally:
            for handler in list(channel.driver.log.handlers):
                if isinstance(handler, logging.FileHandler):
                    channel.driver.log.removeHandler(handler)
                    handler.close()

    def test_daily_channel_writes_dated_file(self):
        import tempfile

        directory = tempfile.mkdtemp()
        channel = DailyChannel(driver="daily", path=directory)
        try:
            self.assertIsInstance(channel.driver, LogSingleDriver)
            self.assertTrue(channel.driver.path.endswith(".log"))
        finally:
            for handler in list(channel.driver.log.handlers):
                if isinstance(handler, logging.FileHandler):
                    channel.driver.log.removeHandler(handler)
                    handler.close()

    def test_stack_channel_collects_known_channels(self):
        channel = StackChannel(channels=["terminal"])
        self.assertEqual(len(channel.channels), 1)
        self.assertIsInstance(channel.channels[0], TerminalChannel)

    def test_stack_channel_ignores_unknown_channels(self):
        channel = StackChannel(channels=["nope-not-real"])
        self.assertEqual(channel.channels, [])

    def test_stack_channel_respects_level_thresholds(self):
        channel = StackChannel(channels=["terminal"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            channel.info("shown")
        self.assertIn("shown", buffer.getvalue())

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            channel.debug("hidden")
        # terminal level is "info", so debug is filtered out
        self.assertEqual(buffer.getvalue(), "")


class LoggerFacadeTest(unittest.TestCase):
    def setUp(self):
        self.app = get_app()
        self._had_logger = False
        try:
            self._previous = self.app.make("logger")
            self._had_logger = True
        except Exception:
            self._previous = None
        self.channel = MagicMock()
        self.app.bind("logger", self.channel)
        Logger.instance = None

    def tearDown(self):
        Logger.instance = None
        if self._had_logger:
            self.app.bind("logger", self._previous)

    def test_level_methods_delegate_to_resolved_channel(self):
        Logger.info("hello")
        self.channel.info.assert_called_once()
        (message,), _ = self.channel.info.call_args
        self.assertTrue(message.endswith("hello"))
        self.assertIn(" - ", message)

    def test_error_and_debug_delegate(self):
        Logger.error("bad")
        Logger.debug("trace")
        self.channel.error.assert_called_once()
        self.channel.debug.assert_called_once()

    def test_log_dispatches_to_named_level(self):
        with patch.object(Logger, "info") as info_mock:
            Logger.log("INFO", "x")
            info_mock.assert_called_once_with("x")

    def test_log_falls_back_to_error_for_unknown_level(self):
        with patch.object(Logger, "error") as error_mock:
            Logger.log("bogus", "x")
            error_mock.assert_called_once_with("x")

    def test_logger_info_returns_caller_location(self):
        info = Logger.logger_info()
        self.assertIsInstance(info, str)
        self.assertIn(" - ", info)
        self.assertNotIn("logging/logger.py", info)


class LoggingManagerTest(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        self._handlers = list(self.root.handlers)

    def tearDown(self):
        for handler in list(self.root.handlers):
            if handler not in self._handlers:
                self.root.removeHandler(handler)

    def test_channel_delegates_to_channel_factory(self):
        sentinel = object()
        factory = MagicMock()
        factory.make.return_value = MagicMock(return_value=sentinel)
        manager = LoggingManager(channel_factory=factory, driver_factory=None)
        self.assertIs(manager.channel("single"), sentinel)
        factory.make.assert_called_once_with("single")

    def test_configure_python_logging_installs_handler_once(self):
        root = logging.getLogger()
        LoggingManager.configure_python_logging()
        LoggingManager.configure_python_logging()
        installed = [h for h in root.handlers if isinstance(h, LoggingHandler)]
        self.assertEqual(len(installed), 1)


class LoggingHandlerTest(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        self._handlers = list(self.root.handlers)

    def tearDown(self):
        for handler in list(self.root.handlers):
            if handler not in self._handlers:
                self.root.removeHandler(handler)

    def test_emit_forwards_record_to_logger(self):
        handler = LoggingHandler()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="kaboom", args=(), exc_info=None,
        )
        with patch("fastapi_startkit.logging.logger.Logger.log") as log_mock:
            handler.emit(record)
            log_mock.assert_called_once()
            args, _ = log_mock.call_args
            self.assertEqual(args[0], "ERROR")
            self.assertIn("kaboom", args[1])

    def test_install_is_idempotent(self):
        root = logging.getLogger()
        LoggingHandler.install()
        LoggingHandler.install()
        self.assertEqual(len([h for h in root.handlers if isinstance(h, LoggingHandler)]), 1)


class MakeDirectoryTest(unittest.TestCase):
    def test_returns_false_for_existing_file(self):
        import tempfile
        import os

        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            self.assertFalse(make_directory(path))
        finally:
            os.remove(path)

    def test_creates_missing_parent_directories(self):
        import tempfile
        import os

        base = tempfile.mkdtemp()
        target = os.path.join(base, "nested", "deep", "file.log")
        self.assertTrue(make_directory(target))
        self.assertTrue(os.path.isdir(os.path.join(base, "nested", "deep")))

    def test_returns_true_without_recreating_existing_parent(self):
        import tempfile
        import os

        base = tempfile.mkdtemp()
        target = os.path.join(base, "file.log")
        self.assertTrue(make_directory(target))
        self.assertFalse(os.path.isfile(target))


class LoggingConfigTest(unittest.TestCase):
    def test_default_channels_are_present(self):
        config = LoggingConfig()
        self.assertIn("stack", config.channels)
        self.assertIn("daily", config.channels)
        self.assertIn("terminal", config.channels)
        self.assertIsInstance(config.default, str)

    def test_channel_dataclass_defaults(self):
        self.assertEqual(config_channels.SingleChannel().driver, "single")
        self.assertEqual(config_channels.SingleChannel().level, "debug")
        self.assertEqual(config_channels.StackChannel().channels, ["daily", "terminal"])
        self.assertEqual(config_channels.DailyChannel().driver, "daily")
        self.assertEqual(config_channels.TerminalChannel().level, "info")
        self.assertEqual(config_channels.SlackChannel().driver, "slack")
        self.assertEqual(config_channels.SyslogChannel().path, "/var/run/syslog")


class ListenerTest(unittest.TestCase):
    def test_handle_logs_exception_details(self):
        logger = MagicMock()
        listener = LoggerExceptionListener(logger)
        self.assertEqual(listener.listens, ["*"])
        listener.handle(ValueError("nope"), "app.py", 42)
        logger.error.assert_called_once()
        (message,), _ = logger.error.call_args
        self.assertIn("ValueError", message)
        self.assertIn("app.py", message)
        self.assertIn("42", message)


class LogProviderTest(unittest.TestCase):
    def test_register_binds_factories_and_manager(self):
        application = get_app()
        LogProvider(application).register()
        # The container auto-resolves bound classes into instances on make().
        self.assertIsInstance(application.make("LogChannelFactory"), ChannelFactory)
        self.assertIsInstance(application.make("LogDriverFactory"), DriverFactory)
        self.assertIsInstance(application.make("LoggingManager"), LoggingManager)

    def test_register_merges_default_config(self):
        from fastapi_startkit.facades import Config

        application = get_app()
        LogProvider(application).register()
        self.assertEqual(Config.get("logging.default"), "stack")

    def test_boot_binds_and_swaps_logger_channel(self):
        application = get_app()
        provider = LogProvider(application)
        provider.register()
        config = application.make("config")
        original_default = config.get("logging.default")
        config.set("logging.default", "terminal")
        try:
            provider.boot()
            self.assertIsInstance(application.make("logger"), TerminalChannel)
            self.assertIn("logging", application.published_resources)
        finally:
            config.set("logging.default", original_default)

    def test_boot_returns_early_when_no_default_channel(self):
        mock_app = MagicMock()
        mock_app.make.return_value.get.return_value = None
        provider = LogProvider(mock_app)
        provider.boot()
        called_keys = [call.args[0] for call in mock_app.make.call_args_list if call.args]
        self.assertNotIn("LoggingManager", called_keys)


if __name__ == "__main__":
    unittest.main()

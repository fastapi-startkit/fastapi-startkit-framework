import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.application import Application, app as get_app
from fastapi_startkit.container.container import Container
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

ALL_LEVELS = ("emergency", "alert", "critical", "error", "warning", "notice", "info", "debug")


@pytest.fixture(scope="module", autouse=True)
def booted_app():
    """Boot a testing Application with the LogProvider so the logging config,
    the channel/driver factories, and the `logger` channel are wired up exactly
    as they are at runtime — the framework does the registration, not the test.

    Booting installs a global LoggingHandler on the real root logger and swaps
    the global app singleton, so both are captured here and restored on teardown
    to stop this module's setup from leaking into other tests.
    """
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        saved_app = Container.instance()
    except Exception:
        saved_app = None

    Application(env="testing", providers=[LogProvider])
    yield

    for handler in list(root.handlers):
        if handler not in saved_handlers:
            root.removeHandler(handler)
    root.setLevel(saved_level)
    Logger.instance = None
    if saved_app is not None:
        Container.set_instance(saved_app)


@pytest.fixture
def isolated_named_root():
    """Isolate the "root"-named logger the single/syslog drivers write through:
    disable propagation so records do not reach the installed LoggingHandler, and
    remove any handlers the test attaches so they do not leak into other tests."""
    root_named = logging.getLogger("root")
    propagate = root_named.propagate
    root_named.propagate = False
    existing = list(root_named.handlers)
    yield root_named
    for handler in list(root_named.handlers):
        if handler not in existing:
            root_named.removeHandler(handler)
            handler.close()
    root_named.propagate = propagate


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


class TestChannelFactory:
    def test_make_returns_registered_channel_classes(self):
        assert ChannelFactory.make("single") is SingleChannel
        assert ChannelFactory.make("daily") is DailyChannel
        assert ChannelFactory.make("terminal") is TerminalChannel
        assert ChannelFactory.make("stack") is StackChannel

    def test_make_returns_none_for_unknown_channel(self):
        assert ChannelFactory.make("does-not-exist") is None

    def test_register_adds_new_channels(self):
        marker = object()
        try:
            ChannelFactory.register({"custom_test_channel": marker})
            assert ChannelFactory.make("custom_test_channel") is marker
        finally:
            ChannelFactory.channels.pop("custom_test_channel", None)


class TestDriverFactory:
    def test_make_maps_names_to_driver_classes(self):
        assert DriverFactory.make("single") is LogSingleDriver
        assert DriverFactory.make("daily") is LogSingleDriver
        assert DriverFactory.make("slack") is LogSlackDriver
        assert DriverFactory.make("syslog") is LogSyslogDriver
        assert DriverFactory.make("terminal") is LogTerminalDriver

    def test_make_returns_none_for_unknown_driver(self):
        assert DriverFactory.make("unknown") is None


class TestBaseDriverShouldRun:
    @pytest.fixture
    def driver(self):
        return BaseDriver()

    def test_returns_true_when_no_max_level(self, driver):
        assert driver.should_run("debug", None)

    def test_more_severe_level_runs_under_a_less_severe_threshold(self, driver):
        # error (index 3) is more severe than info (index 6)
        assert driver.should_run("error", "info")

    def test_less_severe_level_is_filtered_out(self, driver):
        # debug (index 7) is less severe than info (index 6)
        assert not driver.should_run("debug", "info")

    def test_equal_level_runs(self, driver):
        assert driver.should_run("info", "info")

    def test_get_time_returns_formatted_datetime(self, driver):
        assert isinstance(driver.get_time().to_datetime_string(), str)


class TestBaseChannel:
    def _channel(self, should_run=True, max_level="debug"):
        channel = BaseChannel()
        channel.driver = RecordingDriver(should_run=should_run)
        channel.max_level = max_level
        return channel

    def test_level_methods_delegate_to_driver_when_allowed(self):
        channel = self._channel(should_run=True)
        for level in ALL_LEVELS:
            result = getattr(channel, level)("message")
            assert result == f"{level}:message"
        assert len(channel.driver.calls) == 8

    def test_level_methods_are_suppressed_when_not_allowed(self):
        channel = self._channel(should_run=False)
        assert channel.info("message") is None
        assert channel.error("message") is None
        assert channel.driver.calls == []

    def test_log_reports_whether_level_should_run(self):
        assert self._channel(should_run=True).log("info", "m")
        assert not self._channel(should_run=False).log("info", "m")

    def test_channel_builds_a_new_channel_instance(self):
        channel = self._channel()
        assert isinstance(channel.channel("terminal"), TerminalChannel)


class TestMultiBaseChannel:
    def _multi(self, should_run=True):
        inner = BaseChannel()
        inner.driver = RecordingDriver(should_run=should_run)
        inner.max_level = "debug"
        multi = MultiBaseChannel()
        multi.channels = [inner]
        return multi, inner

    def test_broadcasts_each_level_to_all_channels(self):
        multi, inner = self._multi(should_run=True)
        for level in ALL_LEVELS:
            getattr(multi, level)("message")
        recorded = [level for level, _ in inner.driver.calls]
        assert recorded == list(ALL_LEVELS)

    def test_skips_channels_that_should_not_run(self):
        multi, inner = self._multi(should_run=False)
        multi.info("message")
        multi.error("message")
        assert inner.driver.calls == []


class TestTerminalDriver:
    @pytest.fixture
    def driver(self):
        return LogTerminalDriver()

    def test_get_format_includes_time_level_and_message(self, driver):
        formatted = driver.get_format("hello", "INFO")
        assert "INFO" in formatted
        assert "hello" in formatted
        assert re.search(r"\d{4}-\d{2}-\d{2}", formatted)

    def test_each_level_writes_to_stdout(self, driver, capsys):
        for level, method in (
            ("EMERGENCY", driver.emergency),
            ("ALERT", driver.alert),
            ("CRITICAL", driver.critical),
            ("ERROR", driver.error),
            ("WARNING", driver.warning),
            ("NOTICE", driver.notice),
            ("INFO", driver.info),
            ("DEBUG", driver.debug),
        ):
            method("payload")
            output = capsys.readouterr().out
            assert level in output
            assert "payload" in output


class TestSingleDriver:
    def test_writes_formatted_levels_to_the_file(self, tmp_path, isolated_named_root):
        path = tmp_path / "single.log"
        driver = LogSingleDriver(path=str(path), max_level="debug")
        driver.error("boom")
        driver.info("ping")
        contents = path.read_text()
        assert "ERROR" in contents
        assert "boom" in contents
        assert "INFO" in contents
        assert "ping" in contents

    def test_change_format_replaces_handlers(self, tmp_path, isolated_named_root):
        path = tmp_path / "single.log"
        driver = LogSingleDriver(path=str(path), max_level="debug")
        before = len(driver.log.handlers)
        driver.change_format("%(message)s")
        assert len(driver.log.handlers) <= before
        assert len(driver.log.handlers) >= 1


class TestSlackDriver:
    def _driver(self):
        return LogSlackDriver(token="tok", channel="#bot", username="bot", emoji=":x:")

    def test_get_format_includes_level_and_message(self):
        formatted = self._driver().get_format("hi", "ERROR")
        assert "ERROR" in formatted
        assert "hi" in formatted

    def test_level_methods_post_to_slack(self):
        driver = self._driver()
        with (
            patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock,
            patch.object(driver, "find_channel", return_value="C123"),
        ):
            driver.error("boom")
            requests_mock.post.assert_called_once()
            url, payload = requests_mock.post.call_args.args
            # Assert the concrete Slack endpoint, not driver.slack_url (that would be
            # circular — it is the value that produced the call).
            assert url == "https://slack.com/api/chat.postMessage"
            assert "boom" in payload["text"]
            assert "ERROR" in payload["text"]
            assert payload["token"] == "tok"
            assert payload["channel"] == "C123"
            assert payload["username"] == "bot"

    def test_find_channel_resolves_channel_id(self):
        driver = self._driver()
        response = MagicMock()
        response.json.return_value = {"channels": [{"name": "bot", "id": "C123"}]}
        with patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock:
            requests_mock.post.return_value = response
            assert driver.find_channel("#bot") == "C123"

    def test_find_channel_raises_when_missing(self):
        driver = self._driver()
        response = MagicMock()
        response.json.return_value = {"channels": [{"name": "other", "id": "C999"}]}
        with patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests") as requests_mock:
            requests_mock.post.return_value = response
            with pytest.raises(Exception):
                driver.find_channel("#bot")


class TestSyslogDriver:
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


class TestTimezoneAwareLogFile:
    """The daily log file name comes from get_time(), which resolves
    `logging.channels.timezone` — so the file that gets generated on disk must
    follow the application's configured timezone, not the machine/UTC clock."""

    @pytest.fixture(autouse=True)
    def _config(self, isolated_named_root):
        self.config = get_app().make("config")
        yield
        # Restore to the code's default so other tests' get_time() keeps working.
        self.config.set("logging.channels.timezone", "UTC")

    def _daily_path(self, directory, tz, fixed_instant):
        self.config.set("logging.channels.timezone", tz)
        with patch("pendulum.now", return_value=fixed_instant):
            return DailyChannel(driver="daily", path=directory).driver.path

    def test_daily_file_date_follows_configured_timezone(self, tmp_path):
        import pendulum

        # 23:30 UTC sits on a day boundary: timezones ahead of UTC are already on
        # the next calendar day, timezones behind are still on the previous one.
        fixed = pendulum.datetime(2026, 7, 8, 23, 30, 0, tz="UTC")
        directory = str(tmp_path)

        ahead = self._daily_path(directory, "Pacific/Kiritimati", fixed)  # UTC+14
        behind = self._daily_path(directory, "Pacific/Honolulu", fixed)  # UTC-10

        # File names differ purely because of the configured timezone.
        assert ahead.endswith("2026-07-09.log"), ahead
        assert behind.endswith("2026-07-08.log"), behind
        assert ahead != behind

        # And both files are actually created on disk with the tz-derived names.
        assert (tmp_path / "2026-07-09.log").is_file()
        assert (tmp_path / "2026-07-08.log").is_file()

    def test_get_time_reflects_configured_timezone(self):
        import pendulum

        fixed = pendulum.datetime(2026, 7, 8, 23, 30, 0, tz="UTC")
        self.config.set("logging.channels.timezone", "Pacific/Kiritimati")
        with patch("pendulum.now", return_value=fixed):
            now = BaseDriver().get_time()
        assert now.to_date_string() == "2026-07-09"
        assert now.timezone_name == "Pacific/Kiritimati"


class TestChannelConstruction:
    @staticmethod
    def _close_file_handlers(driver):
        for handler in list(driver.log.handlers):
            if isinstance(handler, logging.FileHandler):
                driver.log.removeHandler(handler)
                handler.close()

    def test_terminal_channel_uses_terminal_driver(self):
        channel = TerminalChannel()
        assert channel.max_level == "info"
        assert isinstance(channel.driver, LogTerminalDriver)

    def test_single_channel_builds_single_driver(self, tmp_path):
        channel = SingleChannel(driver="single", path=str(tmp_path / "single.log"))
        try:
            assert isinstance(channel.driver, LogSingleDriver)
        finally:
            self._close_file_handlers(channel.driver)

    def test_daily_channel_writes_dated_file(self, tmp_path):
        channel = DailyChannel(driver="daily", path=str(tmp_path))
        try:
            assert isinstance(channel.driver, LogSingleDriver)
            assert channel.driver.path.endswith(".log")
        finally:
            self._close_file_handlers(channel.driver)

    def test_stack_channel_collects_known_channels(self):
        channel = StackChannel(channels=["terminal"])
        assert len(channel.channels) == 1
        assert isinstance(channel.channels[0], TerminalChannel)

    def test_stack_channel_ignores_unknown_channels(self):
        channel = StackChannel(channels=["nope-not-real"])
        assert channel.channels == []

    def test_stack_channel_respects_level_thresholds(self, capsys):
        channel = StackChannel(channels=["terminal"])
        channel.info("shown")
        assert "shown" in capsys.readouterr().out

        channel.debug("hidden")
        # terminal level is "info", so debug is filtered out
        assert capsys.readouterr().out == ""


class TestLoggerFacade:
    @pytest.fixture(autouse=True)
    def _bind_logger(self):
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
        yield
        Logger.instance = None
        if self._had_logger:
            self.app.bind("logger", self._previous)

    def test_level_methods_delegate_to_resolved_channel(self):
        Logger.info("hello")
        self.channel.info.assert_called_once()
        (message,), _ = self.channel.info.call_args
        assert message.endswith("hello")
        assert " - " in message

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
        assert isinstance(info, str)
        assert " - " in info
        assert "logging/logger.py" not in info


class TestLoggingManager:
    @pytest.fixture(autouse=True)
    def _snapshot_root(self):
        root = logging.getLogger()
        handlers = list(root.handlers)
        yield
        for handler in list(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)

    def test_channel_delegates_to_channel_factory(self):
        sentinel = object()
        factory = MagicMock()
        factory.make.return_value = MagicMock(return_value=sentinel)
        manager = LoggingManager(channel_factory=factory, driver_factory=None)
        assert manager.channel("single") is sentinel
        factory.make.assert_called_once_with("single")

    def test_configure_python_logging_installs_handler_once(self):
        root = logging.getLogger()
        LoggingManager.configure_python_logging()
        LoggingManager.configure_python_logging()
        installed = [h for h in root.handlers if isinstance(h, LoggingHandler)]
        assert len(installed) == 1


class TestLoggingHandler:
    @pytest.fixture(autouse=True)
    def _snapshot_root(self):
        root = logging.getLogger()
        handlers = list(root.handlers)
        yield
        for handler in list(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)

    def test_emit_forwards_record_to_logger(self):
        handler = LoggingHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="kaboom",
            args=(),
            exc_info=None,
        )
        with patch("fastapi_startkit.logging.logger.Logger.log") as log_mock:
            handler.emit(record)
            log_mock.assert_called_once()
            args, _ = log_mock.call_args
            assert args[0] == "ERROR"
            assert "kaboom" in args[1]

    def test_install_is_idempotent(self):
        root = logging.getLogger()
        LoggingHandler.install()
        LoggingHandler.install()
        assert len([h for h in root.handlers if isinstance(h, LoggingHandler)]) == 1


class TestMakeDirectory:
    def test_returns_false_for_existing_file(self, tmp_path):
        path = tmp_path / "file"
        path.write_text("")
        assert not make_directory(str(path))

    def test_creates_missing_parent_directories(self, tmp_path):
        target = tmp_path / "nested" / "deep" / "file.log"
        assert make_directory(str(target))
        assert (tmp_path / "nested" / "deep").is_dir()

    def test_returns_true_without_recreating_existing_parent(self, tmp_path):
        target = tmp_path / "file.log"
        assert make_directory(str(target))
        assert not target.is_file()


class TestLoggingConfig:
    def test_default_channels_are_present(self):
        config = LoggingConfig()
        assert "stack" in config.channels
        assert "daily" in config.channels
        assert "terminal" in config.channels
        assert isinstance(config.default, str)

    def test_channel_dataclass_defaults(self):
        assert config_channels.SingleChannel().driver == "single"
        assert config_channels.SingleChannel().level == "debug"
        assert config_channels.StackChannel().channels == ["daily", "terminal"]
        assert config_channels.DailyChannel().driver == "daily"
        assert config_channels.TerminalChannel().level == "info"
        assert config_channels.SlackChannel().driver == "slack"
        assert config_channels.SyslogChannel().path == "/var/run/syslog"


class TestListener:
    def test_handle_logs_exception_details(self):
        logger = MagicMock()
        listener = LoggerExceptionListener(logger)
        assert listener.listens == ["*"]
        listener.handle(ValueError("nope"), "app.py", 42)
        logger.error.assert_called_once()
        (message,), _ = logger.error.call_args
        assert "ValueError" in message
        assert "app.py" in message
        assert "42" in message


class TestLogProvider:
    def test_register_binds_factories_and_manager(self):
        application = get_app()
        LogProvider(application).register()
        # The container auto-resolves bound classes into instances on make().
        assert isinstance(application.make("LogChannelFactory"), ChannelFactory)
        assert isinstance(application.make("LogDriverFactory"), DriverFactory)
        assert isinstance(application.make("LoggingManager"), LoggingManager)

    def test_register_merges_default_config(self):
        from fastapi_startkit.facades import Config

        application = get_app()
        LogProvider(application).register()
        assert Config.get("logging.default") == "stack"

    def test_boot_binds_and_swaps_logger_channel(self):
        application = get_app()
        provider = LogProvider(application)
        provider.register()
        config = application.make("config")
        original_default = config.get("logging.default")
        config.set("logging.default", "terminal")
        try:
            provider.boot()
            assert isinstance(application.make("logger"), TerminalChannel)
            assert "logging" in application.published_resources
        finally:
            config.set("logging.default", original_default)

    def test_boot_returns_early_when_no_default_channel(self):
        mock_app = MagicMock()
        mock_app.make.return_value.get.return_value = None
        provider = LogProvider(mock_app)
        provider.boot()
        called_keys = [call.args[0] for call in mock_app.make.call_args_list if call.args]
        assert "LoggingManager" not in called_keys

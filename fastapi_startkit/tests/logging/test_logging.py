"""Tests for the Logging system (task #12).

Covers: SingleChannel, DailyChannel, StackChannel, TerminalChannel,
SlackChannel, SyslogChannel, and BaseDriver.should_run level filtering.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


@pytest.fixture
def log_file(tmp_path):
    return str(tmp_path / "app.log")


@pytest.fixture
def setup_logging_config(app, log_file, tmp_path):
    """Populate the config with minimal logging settings."""
    cfg = app.make("config")
    cfg.set(
        "logging",
        {
            "channels": {
                "timezone": "UTC",
                "single": {
                    "driver": "single",
                    "path": log_file,
                    "level": "debug",
                },
                "daily": {
                    "driver": "daily",
                    "path": str(tmp_path / "daily"),
                    "level": "debug",
                },
                "stack": {
                    "channels": ["single"],
                },
                "terminal": {
                    "driver": "terminal",
                    "level": "debug",
                },
                "slack": {
                    "driver": "slack",
                    "token": "xoxb-test",
                    "channel": "#general",
                    "emoji": ":warning:",
                    "username": "testbot",
                    "level": "debug",
                },
                "syslog": {
                    "driver": "syslog",
                    "path": str(tmp_path / "syslog.log"),
                    "level": "debug",
                },
            }
        },
    )
    return cfg


# ---------------------------------------------------------------------------
# BaseDriver.should_run — level filtering
# ---------------------------------------------------------------------------


class TestBaseDriverShouldRun:
    def test_no_max_level_always_runs(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        assert driver.should_run("debug", None) is True
        assert driver.should_run("emergency", None) is True

    def test_debug_not_run_when_max_is_error(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        # levels list: emergency(0) > ... > error(3) > ... > debug(7)
        assert driver.should_run("debug", "error") is False

    def test_error_runs_when_max_is_error(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        assert driver.should_run("error", "error") is True

    def test_critical_runs_when_max_is_error(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        assert driver.should_run("critical", "error") is True

    def test_info_not_run_when_max_is_warning(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        assert driver.should_run("info", "warning") is False

    def test_warning_runs_when_max_is_warning(self, app):
        from fastapi_startkit.logging.drivers.BaseDriver import BaseDriver

        driver = BaseDriver()
        assert driver.should_run("warning", "warning") is True


# ---------------------------------------------------------------------------
# SingleChannel — file-based logging
# ---------------------------------------------------------------------------


class TestSingleChannel:
    def test_message_written_to_log_file(self, app, setup_logging_config, log_file):
        # Remove all root logger handlers to avoid cross-test pollution
        root_logger = logging.getLogger("root")
        root_logger.handlers.clear()

        from fastapi_startkit.logging.channels.SingleChannel import SingleChannel

        channel = SingleChannel()
        channel.info("hello single channel")

        # Flush handlers
        for h in logging.getLogger("root").handlers:
            h.flush()

        assert os.path.exists(log_file)
        content = open(log_file).read()
        assert "hello single channel" in content

    def test_level_filtering_blocks_debug_when_max_is_error(self, app, tmp_path):
        cfg = app.make("config")
        filtered_log = str(tmp_path / "filtered.log")
        cfg.set("logging.channels.single.path", filtered_log)
        cfg.set("logging.channels.single.level", "error")
        cfg.set("logging.channels.single.driver", "single")

        root_logger = logging.getLogger("root")
        root_logger.handlers.clear()

        from fastapi_startkit.logging.channels.SingleChannel import SingleChannel

        channel = SingleChannel(path=filtered_log)
        channel.debug("should be blocked")

        for h in logging.getLogger("root").handlers:
            h.flush()

        if os.path.exists(filtered_log):
            content = open(filtered_log).read()
            assert "should be blocked" not in content

    def test_error_level_written(self, app, setup_logging_config, log_file, tmp_path):
        error_log = str(tmp_path / "error_only.log")
        app.make("config").set("logging.channels.single.path", error_log)

        root_logger = logging.getLogger("root")
        root_logger.handlers.clear()

        from fastapi_startkit.logging.channels.SingleChannel import SingleChannel

        channel = SingleChannel(path=error_log)
        channel.error("error message")

        for h in logging.getLogger("root").handlers:
            h.flush()

        assert os.path.exists(error_log)
        content = open(error_log).read()
        assert "error message" in content


# ---------------------------------------------------------------------------
# DailyChannel — date-based log file
# ---------------------------------------------------------------------------


class TestDailyChannel:
    def test_daily_channel_creates_dated_log(self, app, setup_logging_config, tmp_path):
        import pendulum

        daily_dir = str(tmp_path / "daily")
        os.makedirs(daily_dir, exist_ok=True)
        app.make("config").set("logging.channels.daily.path", daily_dir)
        app.make("config").set("logging.channels.daily.driver", "single")
        app.make("config").set("logging.channels.daily.level", "debug")

        root_logger = logging.getLogger("root")
        root_logger.handlers.clear()

        from fastapi_startkit.logging.channels.DailyChannel import DailyChannel

        channel = DailyChannel()
        channel.debug("daily log entry")

        for h in logging.getLogger("root").handlers:
            h.flush()

        today = pendulum.now("UTC").to_date_string()
        expected_file = os.path.join(daily_dir, f"{today}.log")
        assert os.path.exists(expected_file)
        content = open(expected_file).read()
        assert "daily log entry" in content

    def test_daily_channel_different_date_produces_new_file(self, app, setup_logging_config, tmp_path):
        """Mock the date so two channels get different filenames."""
        import pendulum

        daily_dir = str(tmp_path / "daily2")
        os.makedirs(daily_dir, exist_ok=True)
        app.make("config").set("logging.channels.daily.path", daily_dir)
        app.make("config").set("logging.channels.daily.driver", "single")
        app.make("config").set("logging.channels.daily.level", "debug")

        root_logger = logging.getLogger("root")
        root_logger.handlers.clear()

        from fastapi_startkit.logging.channels.DailyChannel import DailyChannel

        # First channel — today
        ch1 = DailyChannel()

        root_logger.handlers.clear()

        # Patch get_time to return a different day
        fake_past = pendulum.datetime(2020, 1, 1, tz="UTC")
        with patch.object(DailyChannel, "get_time", return_value=fake_past):
            ch2 = DailyChannel()

        today = pendulum.now("UTC").to_date_string()
        assert os.path.join(daily_dir, f"{today}.log") != os.path.join(daily_dir, "2020-01-01.log")


# ---------------------------------------------------------------------------
# StackChannel — fans out to multiple channels
# ---------------------------------------------------------------------------


class TestStackChannel:
    def test_stack_channel_delivers_to_all_channels(self, app, setup_logging_config, log_file, tmp_path):
        # Configure a second single channel so the stack can fan out to two
        second_log = str(tmp_path / "second.log")
        app.make("config").set(
            "logging.channels.second",
            {
                "driver": "single",
                "path": second_log,
                "level": "debug",
            },
        )

        from fastapi_startkit.logging.channels.StackChannel import StackChannel

        ch1 = MagicMock()
        ch1.driver = MagicMock()
        ch1.driver.should_run.return_value = True
        ch1.max_level = "debug"

        ch2 = MagicMock()
        ch2.driver = MagicMock()
        ch2.driver.should_run.return_value = True
        ch2.max_level = "debug"

        stack = StackChannel(channels=[])
        stack.channels = [ch1, ch2]

        stack.debug("fan-out message")

        ch1.driver.debug.assert_called_once_with("fan-out message")
        ch2.driver.debug.assert_called_once_with("fan-out message")

    def test_stack_channel_skips_channel_when_level_filtered(self, app, setup_logging_config):
        from fastapi_startkit.logging.channels.StackChannel import StackChannel

        ch = MagicMock()
        ch.driver = MagicMock()
        ch.driver.should_run.return_value = False  # filtered out
        ch.max_level = "error"

        stack = StackChannel(channels=[])
        stack.channels = [ch]

        stack.debug("blocked message")

        ch.driver.debug.assert_not_called()

    def test_stack_notice_fans_out(self, app, setup_logging_config):
        from fastapi_startkit.logging.channels.StackChannel import StackChannel

        ch = MagicMock()
        ch.driver = MagicMock()
        ch.driver.should_run.return_value = True
        ch.max_level = "debug"

        stack = StackChannel(channels=[])
        stack.channels = [ch]

        stack.notice("notice message")

        ch.driver.notice.assert_called_once_with("notice message")


# ---------------------------------------------------------------------------
# TerminalChannel — uses print / capsys
# ---------------------------------------------------------------------------


class TestTerminalChannel:
    def test_terminal_channel_info_prints(self, app, setup_logging_config, capsys):
        from fastapi_startkit.logging.channels.TerminalChannel import TerminalChannel

        channel = TerminalChannel()
        channel.info("terminal info message")

        captured = capsys.readouterr()
        assert "terminal info message" in captured.out

    def test_terminal_channel_debug_prints(self, app, setup_logging_config, capsys):
        from fastapi_startkit.logging.channels.TerminalChannel import TerminalChannel

        channel = TerminalChannel()
        channel.debug("terminal debug message")

        captured = capsys.readouterr()
        assert "terminal debug message" in captured.out

    def test_terminal_channel_error_prints(self, app, setup_logging_config, capsys):
        from fastapi_startkit.logging.channels.TerminalChannel import TerminalChannel

        channel = TerminalChannel()
        channel.error("terminal error message")

        captured = capsys.readouterr()
        assert "terminal error message" in captured.out

    def test_terminal_channel_level_filtering(self, app, tmp_path, capsys):
        cfg = app.make("config")
        cfg.set("logging.channels.terminal.driver", "terminal")
        cfg.set("logging.channels.terminal.level", "error")

        from fastapi_startkit.logging.channels.TerminalChannel import TerminalChannel

        channel = TerminalChannel()
        channel.debug("should not appear")

        captured = capsys.readouterr()
        assert "should not appear" not in captured.out


# ---------------------------------------------------------------------------
# SlackChannel — mocked HTTP calls
# ---------------------------------------------------------------------------


class TestSlackChannel:
    def test_slack_channel_posts_message(self, app, setup_logging_config):
        from fastapi_startkit.logging.drivers.LogSlackDriver import LogSlackDriver

        driver = LogSlackDriver(
            token="xoxb-test",
            channel="#general",
            emoji=":warning:",
            username="testbot",
        )

        with (
            patch.object(driver, "find_channel", return_value="C123456") as mock_find,
            patch("fastapi_startkit.logging.drivers.LogSlackDriver.requests.post") as mock_post,
        ):
            driver.send("test slack message")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert call_kwargs[0][0] == "https://slack.com/api/chat.postMessage"

    def test_slack_driver_formats_message(self, app, setup_logging_config):
        from fastapi_startkit.logging.drivers.LogSlackDriver import LogSlackDriver

        driver = LogSlackDriver(token="t", channel="#ch", emoji=":ok:", username="bot")

        with patch.object(driver, "send") as mock_send:
            driver.info("formatted info")
            mock_send.assert_called_once()
            assert "formatted info" in mock_send.call_args[0][0]
            assert "INFO" in mock_send.call_args[0][0]

    def test_slack_driver_error_includes_level(self, app, setup_logging_config):
        from fastapi_startkit.logging.drivers.LogSlackDriver import LogSlackDriver

        driver = LogSlackDriver(token="t", channel="#ch", emoji=":ok:", username="bot")

        with patch.object(driver, "send") as mock_send:
            driver.error("some error")
            assert "ERROR" in mock_send.call_args[0][0]

    def test_slack_driver_warning_includes_level(self, app, setup_logging_config):
        from fastapi_startkit.logging.drivers.LogSlackDriver import LogSlackDriver

        driver = LogSlackDriver(token="t", channel="#ch", emoji=":ok:", username="bot")

        with patch.object(driver, "send") as mock_send:
            driver.warning("a warning")
            assert "WARNING" in mock_send.call_args[0][0]


# ---------------------------------------------------------------------------
# SyslogChannel — uses SysLogHandler (mocked)
# ---------------------------------------------------------------------------


class TestSyslogChannel:
    def test_syslog_driver_adds_handler(self, app, setup_logging_config, tmp_path):
        """SyslogChannel should attach a SysLogHandler to the root logger."""
        from fastapi_startkit.logging.drivers.LogSyslogDriver import LogSyslogDriver

        fake_path = str(tmp_path / "syslog.log")

        with patch("fastapi_startkit.logging.drivers.LogSyslogDriver.logging.handlers.SysLogHandler") as MockHandler:
            instance = MockHandler.return_value
            instance.level = logging.DEBUG

            root_logger = logging.getLogger("root")
            initial_count = len(root_logger.handlers)

            driver = LogSyslogDriver(path=fake_path)

            MockHandler.assert_called_once_with(address=fake_path)

    def test_syslog_driver_info_delegates_to_logger(self, app, setup_logging_config, tmp_path):
        import logging as _logging

        from fastapi_startkit.logging.drivers.LogSyslogDriver import LogSyslogDriver

        fake_path = str(tmp_path / "syslog2.log")
        root_logger = _logging.getLogger("root")

        with patch("fastapi_startkit.logging.drivers.LogSyslogDriver.logging.handlers.SysLogHandler"):
            before = list(root_logger.handlers)
            driver = LogSyslogDriver(path=fake_path)
            mock_log = MagicMock()
            driver.log = mock_log

            driver.info("syslog info test")
            mock_log.info.assert_called_once_with("syslog info test")

        # Remove any mock handlers added during this test so they don't leak
        for h in list(root_logger.handlers):
            if h not in before:
                root_logger.removeHandler(h)

    def test_syslog_driver_error_delegates_to_logger(self, app, setup_logging_config, tmp_path):
        import logging as _logging

        from fastapi_startkit.logging.drivers.LogSyslogDriver import LogSyslogDriver

        fake_path = str(tmp_path / "syslog3.log")
        root_logger = _logging.getLogger("root")

        with patch("fastapi_startkit.logging.drivers.LogSyslogDriver.logging.handlers.SysLogHandler"):
            before = list(root_logger.handlers)
            driver = LogSyslogDriver(path=fake_path)
            mock_log = MagicMock()
            driver.log = mock_log

            driver.error("syslog error test")
            mock_log.error.assert_called_once_with("syslog error test")

        # Remove any mock handlers added during this test so they don't leak
        for h in list(root_logger.handlers):
            if h not in before:
                root_logger.removeHandler(h)


# ---------------------------------------------------------------------------
# ChannelFactory and DriverFactory
# ---------------------------------------------------------------------------


class TestChannelFactory:
    def test_channel_factory_returns_single_channel(self, app):
        from fastapi_startkit.logging.ChannelFactory import ChannelFactory
        from fastapi_startkit.logging.channels.SingleChannel import SingleChannel

        assert ChannelFactory.make("single") is SingleChannel

    def test_channel_factory_returns_daily_channel(self, app):
        from fastapi_startkit.logging.ChannelFactory import ChannelFactory
        from fastapi_startkit.logging.channels.DailyChannel import DailyChannel

        assert ChannelFactory.make("daily") is DailyChannel

    def test_channel_factory_returns_none_for_unknown(self, app):
        from fastapi_startkit.logging.ChannelFactory import ChannelFactory

        assert ChannelFactory.make("unknown_channel") is None

    def test_channel_factory_register_adds_channel(self, app):
        from fastapi_startkit.logging.ChannelFactory import ChannelFactory

        class CustomChannel:
            pass

        ChannelFactory.register({"custom": CustomChannel})
        assert ChannelFactory.make("custom") is CustomChannel

        # Clean up
        del ChannelFactory.channels["custom"]


class TestDriverFactory:
    def test_driver_factory_returns_single_driver(self, app):
        from fastapi_startkit.logging.drivers.LogSingleDriver import LogSingleDriver
        from fastapi_startkit.logging.factory import DriverFactory

        assert DriverFactory.make("single") is LogSingleDriver

    def test_driver_factory_returns_terminal_driver(self, app):
        from fastapi_startkit.logging.drivers.LogTerminalDriver import LogTerminalDriver
        from fastapi_startkit.logging.factory import DriverFactory

        assert DriverFactory.make("terminal") is LogTerminalDriver

    def test_driver_factory_returns_none_for_unknown(self, app):
        from fastapi_startkit.logging.factory import DriverFactory

        assert DriverFactory.make("nonexistent") is None

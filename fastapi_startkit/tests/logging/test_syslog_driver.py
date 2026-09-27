import logging
import unittest
import uuid
from unittest.mock import patch

from fastapi_startkit.logging.drivers.LogSyslogDriver import LogSyslogDriver
from fastapi_startkit.logging.handler import LoggingHandler

SYSLOG_HANDLER = "fastapi_startkit.logging.drivers.LogSyslogDriver.logging.handlers.SysLogHandler"


class RecordingHandler(logging.Handler):
    def __init__(self, address=None):
        super().__init__()
        self.address = address
        self.records: list[logging.LogRecord] = []
        self.closed = False

    def emit(self, record):
        self.records.append(record)

    def close(self):
        self.closed = True
        super().close()


class SyslogDriverRootIsolationTest(unittest.TestCase):
    def setUp(self):
        self.address = f"/tmp/syslog-{uuid.uuid4().hex}"
        self.drivers: list[LogSyslogDriver] = []
        patcher = patch(SYSLOG_HANDLER, side_effect=RecordingHandler)
        self.handler_cls = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for driver in self.drivers:
            driver.close()

    def _driver(self, address=None):
        driver = LogSyslogDriver(path=address or self.address)
        self.drivers.append(driver)
        return driver

    def test_repeated_construction_leaves_root_handlers_and_level_untouched(self):
        root = logging.getLogger()
        handlers_before = list(root.handlers)
        level_before = root.level

        for _ in range(25):
            self._driver()

        self.assertEqual(root.handlers, handlers_before)
        self.assertEqual(root.level, level_before)

    def test_repeated_construction_reuses_one_handler(self):
        first = self._driver()
        for _ in range(24):
            driver = self._driver()
            self.assertIs(driver.handler, first.handler)

        self.handler_cls.assert_called_once_with(address=self.address)
        self.assertEqual(first.log.handlers, [first.handler])
        self.assertFalse(first.log.propagate)

    def test_distinct_addresses_get_distinct_handlers(self):
        first = self._driver()
        second = self._driver(("localhost", 514))

        self.assertIsNot(first.handler, second.handler)
        self.handler_cls.assert_called_with(address=("localhost", 514))

    def test_records_reach_syslog_without_looping_through_the_bridge(self):
        root = logging.getLogger()
        bridge = LoggingHandler()
        root.addHandler(bridge)
        try:
            driver = self._driver()
            with patch.object(LoggingHandler, "emit") as bridge_emit:
                for level in LogSyslogDriver.levels:
                    getattr(driver, level)(f"{level}-message")

            bridge_emit.assert_not_called()
            handler = driver.handler
            assert isinstance(handler, RecordingHandler)
            self.assertEqual(
                [record.getMessage() for record in handler.records],
                [f"{level}-message" for level in LogSyslogDriver.levels],
            )
        finally:
            root.removeHandler(bridge)

    def test_close_detaches_and_closes_the_handler(self):
        driver = self._driver()
        handler = driver.handler
        assert isinstance(handler, RecordingHandler)

        driver.close()
        self.drivers.remove(driver)

        self.assertEqual(driver.log.handlers, [])
        self.assertTrue(handler.closed)

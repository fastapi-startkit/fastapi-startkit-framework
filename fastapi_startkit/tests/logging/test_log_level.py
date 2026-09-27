import logging
import unittest

from fastapi_startkit.logging.config import LoggingConfig
from fastapi_startkit.logging.handler import LoggingHandler
from fastapi_startkit.logging.managers import LoggingManager


class RootLogLevelTest(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger()
        self._handlers = list(self.root.handlers)
        self._level = self.root.level

    def tearDown(self):
        for handler in list(self.root.handlers):
            if handler not in self._handlers:
                self.root.removeHandler(handler)
        self.root.setLevel(self._level)

    def test_install_without_level_leaves_root_level_untouched(self):
        self.root.setLevel(logging.WARNING)
        LoggingHandler.install()
        self.assertEqual(self.root.level, logging.WARNING)

    def test_manager_applies_configured_info_level(self):
        self.root.setLevel(logging.WARNING)
        LoggingManager(level="info")
        self.assertEqual(self.root.level, logging.INFO)

    def test_configured_level_is_applied_even_when_handler_already_installed(self):
        LoggingHandler.install("debug")
        LoggingHandler.install("error")
        self.assertEqual(self.root.level, logging.ERROR)
        self.assertEqual(len([h for h in self.root.handlers if isinstance(h, LoggingHandler)]), 1)

    def test_framework_only_levels_map_to_stdlib_levels(self):
        LoggingHandler.install("notice")
        self.assertEqual(self.root.level, logging.INFO)
        LoggingHandler.install("emergency")
        self.assertEqual(self.root.level, logging.CRITICAL)

    def test_logging_config_defaults_to_info(self):
        self.assertEqual(LoggingConfig().level, "info")


if __name__ == "__main__":
    unittest.main()

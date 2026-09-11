import os
import unittest
from dataclasses import dataclass, field
from typing import assert_type

from fastapi_startkit.environment import env


class EnvTest(unittest.TestCase):
    def setUp(self):
        # Remove any test keys before each case
        for key in ("TEST_STR", "TEST_INT", "TEST_BOOL", "TEST_CAST"):
            os.environ.pop(key, None)

    def tearDown(self):
        for key in ("TEST_STR", "TEST_INT", "TEST_BOOL", "TEST_CAST"):
            os.environ.pop(key, None)

    def test_plain_string_returned_as_str(self):
        os.environ["TEST_STR"] = "hello"
        self.assertEqual(env("TEST_STR"), "hello")
        self.assertIsInstance(env("TEST_STR"), str)

    def test_numeric_string_cast_to_int(self):
        os.environ["TEST_INT"] = "6379"
        self.assertEqual(env("TEST_INT"), 6379)
        self.assertIsInstance(env("TEST_INT"), int)

    def test_zero_string_cast_to_int(self):
        os.environ["TEST_INT"] = "0"
        self.assertEqual(env("TEST_INT"), 0)
        self.assertIsInstance(env("TEST_INT"), int)

    # ── boolean auto-cast ─────────────────────────────────────────────────────

    def test_true_lowercase_cast_to_bool(self):
        os.environ["TEST_BOOL"] = "true"
        self.assertIs(env("TEST_BOOL"), True)

    def test_True_titlecase_cast_to_bool(self):
        os.environ["TEST_BOOL"] = "True"
        self.assertIs(env("TEST_BOOL"), True)

    def test_false_lowercase_cast_to_bool(self):
        os.environ["TEST_BOOL"] = "false"
        self.assertIs(env("TEST_BOOL"), False)

    def test_False_titlecase_cast_to_bool(self):
        os.environ["TEST_BOOL"] = "False"
        self.assertIs(env("TEST_BOOL"), False)

    def test_missing_key_returns_given_default(self):
        self.assertIs(env("TEST_BOOL", False), False)

    def test_missing_key_returns_none_when_default_is_none(self):
        self.assertIsNone(env("TEST_BOOL", None))

    def test_missing_key_returns_string_default(self):
        self.assertEqual(env("TEST_STR", "fallback"), "fallback")

    def test_typed_defaults_are_preserved_in_dataclass_factories(self):
        @dataclass
        class StorageConfig:
            default: str = field(default_factory=lambda: env("FILESYSTEM_DISK", "local"))

        assert_type(env("TEST_STR", "fallback"), str)
        assert_type(env("TEST_INT", 6379), int)
        assert_type(env("TEST_BOOL", False), bool)
        assert_type(env("TEST_NONE", None), None)
        assert_type(env("TEST_CAST", cast=False), str)
        assert_type(env("TEST_BOOL", False, cast=False), str | bool)

        self.assertIsInstance(StorageConfig().default, str)

    def test_cast_false_keeps_numeric_as_str(self):
        os.environ["TEST_CAST"] = "6379"
        self.assertEqual(env("TEST_CAST", cast=False), "6379")
        self.assertIsInstance(env("TEST_CAST", cast=False), str)

    def test_cast_false_keeps_true_as_str(self):
        os.environ["TEST_CAST"] = "true"
        self.assertEqual(env("TEST_CAST", cast=False), "true")
        self.assertIsInstance(env("TEST_CAST", cast=False), str)

    def test_cast_false_keeps_false_as_str(self):
        os.environ["TEST_CAST"] = "false"
        self.assertEqual(env("TEST_CAST", cast=False), "false")
        self.assertIsInstance(env("TEST_CAST", cast=False), str)

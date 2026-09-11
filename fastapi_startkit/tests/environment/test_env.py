import os
import unittest
from dataclasses import dataclass, field
from typing import assert_type

from fastapi_startkit.environment import env


class EnvTest(unittest.TestCase):
    def setUp(self):
        # Remove any test keys before each case
        for key in ("TEST_STR", "TEST_INT", "TEST_BOOL", "TEST_NONE", "TEST_CAST", "FILESYSTEM_DISK"):
            os.environ.pop(key, None)

    def tearDown(self):
        for key in ("TEST_STR", "TEST_INT", "TEST_BOOL", "TEST_NONE", "TEST_CAST", "FILESYSTEM_DISK"):
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

    def test_missing_key_returns_integer_default(self):
        self.assertEqual(env("TEST_INT", 6379), 6379)

    def test_missing_key_returns_none_when_default_is_none(self):
        self.assertIsNone(env("TEST_BOOL", None))

    def test_missing_key_returns_string_default(self):
        self.assertEqual(env("TEST_STR", "fallback"), "fallback")

    def test_typed_defaults_fix_the_return_type(self):
        @dataclass
        class StorageConfig:
            default: str = field(default_factory=lambda: env("FILESYSTEM_DISK", "local"))

        assert_type(env("TEST_STR", "fallback"), str)
        assert_type(env("TEST_INT", 6379), int)
        assert_type(env("TEST_INT", 1.5), float)
        assert_type(env("TEST_BOOL", False), bool)
        assert_type(env("TEST_NONE", None), str | int | bool | None)
        assert_type(env("TEST_NONE", None, cast=False), str | None)
        assert_type(env("TEST_NONE", None, False), str | None)
        assert_type(env("TEST_CAST"), str | int | bool)
        assert_type(env("TEST_CAST", cast=False), str)
        assert_type(env("TEST_BOOL", False, cast=False), str | bool)
        assert_type(env("TEST_BOOL", False, False), str | bool)
        assert_type(env("TEST_BOOL", False, cast=True), bool)
        assert_type(env("TEST_BOOL", False, True), bool)

        self.assertIsInstance(StorageConfig().default, str)

    def test_present_values_cast_to_supplied_default_type(self):
        cases = (
            ("TEST_STR", "6379", "fallback", "6379", str),
            ("TEST_INT", "6379", 1, 6379, int),
            ("TEST_INT", "1.25", 1.0, 1.25, float),
            ("TEST_BOOL", "false", True, False, bool),
        )
        for key, raw, default, expected, expected_type in cases:
            with self.subTest(default=default):
                os.environ[key] = raw
                result = env(key, default)
                self.assertEqual(result, expected)
                self.assertIs(type(result), expected_type)

    def test_invalid_typed_conversions_raise_value_error(self):
        cases = (("TEST_INT", "nope", 1), ("TEST_INT", "1.2", 1), ("TEST_BOOL", "yes", False))
        for key, raw, default in cases:
            with self.subTest(default=default):
                os.environ[key] = raw
                with self.assertRaises(ValueError):
                    env(key, default)

    def test_present_string_stays_string_with_none_default(self):
        os.environ["TEST_NONE"] = "local"

        self.assertEqual(env("TEST_NONE", None), "local")

    def test_none_default_preserves_legacy_auto_casting(self):
        os.environ["TEST_NONE"] = "6379"

        result = env("TEST_NONE", None)

        self.assertEqual(result, 6379)
        self.assertIs(type(result), int)

    def test_dataclass_string_default_stays_string(self):
        os.environ["FILESYSTEM_DISK"] = "6379"

        @dataclass
        class StorageConfig:
            default: str = field(default_factory=lambda: env("FILESYSTEM_DISK", "local"))

        config = StorageConfig()
        self.assertEqual(config.default, "6379")
        self.assertIs(type(config.default), str)

    def test_cast_false_keyword_returns_present_string_with_bool_default(self):
        os.environ["TEST_CAST"] = "6379"

        result = env("TEST_CAST", False, cast=False)

        self.assertEqual(result, "6379")
        self.assertIsInstance(result, str)

    def test_cast_false_third_positional_returns_raw_string(self):
        os.environ["TEST_CAST"] = "6379"

        result = env("TEST_CAST", False, False)

        self.assertEqual(result, "6379")
        self.assertIsInstance(result, str)

    def test_cast_true_keyword_uses_default_type(self):
        os.environ["TEST_CAST"] = "6379"

        self.assertEqual(env("TEST_CAST", 1, cast=True), 6379)

    def test_cast_true_third_positional_uses_default_type(self):
        os.environ["TEST_CAST"] = "false"

        self.assertIs(env("TEST_CAST", True, True), False)

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

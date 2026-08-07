import os
import unittest
from pathlib import Path

from config.redis import RedisConfig

from fastapi_startkit import Config


class ConfigTest(unittest.TestCase):
    def test_it_loads_env_from_arguments(self):
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        from fastapi_startkit import Application

        # We initialize the application with no env, so it should load the default env
        Application(base_path=Path(__file__).resolve().parent.parent)

        self.assertEqual(RedisConfig().host, "host.default")
        self.assertEqual(RedisConfig().port, 0000)
        self.assertEqual(RedisConfig().db, 0)

        # We initialize the application with production env, so it should load the production env
        Application(base_path=Path(__file__).resolve().parent.parent, env="production")

        self.assertEqual(RedisConfig().host, "host.production")
        self.assertEqual(RedisConfig().port, 1111)
        self.assertEqual(RedisConfig().db, 1)

        # We initialize the application with testing env, so it should load the testing env
        Application(base_path=Path(__file__).resolve().parent.parent, env="testing")
        self.assertEqual(RedisConfig().host, "host.testing")
        self.assertEqual(RedisConfig().port, 2222)
        self.assertEqual(RedisConfig().db, 2)

        # We initialize the application with wrong env, so it should load the default env
        Application(base_path=Path(__file__).resolve().parent.parent, env="wrong-env")
        self.assertEqual(RedisConfig().host, "host.default")
        self.assertEqual(RedisConfig().port, 0000)
        self.assertEqual(RedisConfig().db, 0)

    def test_app_loads_env_data(self):
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        from bootstrap.application import app

        self.assertEqual(RedisConfig().host, "host.default")
        self.assertEqual(RedisConfig().port, 0000)
        self.assertEqual(RedisConfig().db, 0)

        app.set_environment("testing")
        app.load_environment()
        self.assertEqual(RedisConfig().host, "host.testing")
        self.assertEqual(RedisConfig().port, 2222)
        self.assertEqual(RedisConfig().db, 2)

        app.set_environment("production")
        app.load_environment()

        self.assertEqual(RedisConfig().host, "host.production")
        self.assertEqual(RedisConfig().port, 1111)
        self.assertEqual(RedisConfig().db, 1)


class ConfigFacadeTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("PYTEST_CURRENT_TEST", None)
        from fastapi_startkit import Application

        self.app = Application(base_path=Path(__file__).resolve().parent.parent)
        Config.set("redis", RedisConfig())

    def test_get_string_field(self):
        self.assertEqual(Config.get("redis.host"), "host.default")

    def test_get_int_field(self):
        self.assertEqual(Config.get("redis.port"), 0)
        self.assertIsInstance(Config.get("redis.port"), int)

    def test_get_dict_field(self):
        self.assertEqual(Config.get("redis.options"), {"decode_responses": True})

    def test_get_nested_dotted_key(self):
        self.assertIs(Config.get("redis.options.decode_responses"), True)

    def test_has_existing_key(self):
        self.assertTrue(Config.has("redis"))

    def test_has_missing_key(self):
        self.assertFalse(Config.has("redis.nonexistent"))

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(Config.get("redis.nonexistent"))

    def test_get_missing_key_returns_default(self):
        self.assertEqual(Config.get("redis.nonexistent", "fallback"), "fallback")

    def test_set_overrides_value_at_runtime(self):
        Config.set("redis.host", "overridden-host")
        self.assertEqual(Config.get("redis.host"), "overridden-host")

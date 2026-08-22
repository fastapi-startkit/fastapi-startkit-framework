import unittest

from fastapi_startkit.exceptions.exceptions import DriverNotFound
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory


class TestConnectionFactoryBuildUrl(unittest.TestCase):
    """Assert that ConnectionFactory.build_url() produces correct SQLAlchemy URLs."""

    def test_mysql_config(self):
        config = {
            "driver": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "mydb",
            "username": "root",
            "password": "secret",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "mysql+aiomysql://root:secret@localhost:3306/mydb")

    def test_postgres_config(self):
        config = {
            "driver": "postgres",
            "host": "db.example.com",
            "port": 5432,
            "database": "mydb",
            "username": "user",
            "password": "pass",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "postgresql+asyncpg://user:pass@db.example.com:5432/mydb")

    def test_sqlite_config_relative_database(self):
        config = {
            "driver": "sqlite",
            "database": "database.sqlite",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "sqlite+aiosqlite:///database.sqlite")

    def test_sqlite_config_absolute_database(self):
        config = {
            "driver": "sqlite",
            "database": "/var/data/database.sqlite",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "sqlite+aiosqlite:////var/data/database.sqlite")

    def test_sqlite_config_ignores_host_user_password_port(self):
        """SQLite has no host/user/password/port -- extra keys must not leak into the URL."""
        config = {
            "driver": "sqlite",
            "database": "database.sqlite",
            "host": "localhost",
            "username": "root",
            "password": "secret",
            "port": "",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "sqlite+aiosqlite:///database.sqlite")

    def test_sqlite_config_via_url_passthrough(self):
        config = {
            "driver": "sqlite",
            "url": "sqlite+aiosqlite:///db.sqlite3",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "sqlite+aiosqlite:///db.sqlite3")

    def test_direct_url_passthrough_takes_precedence(self):
        """If config contains a 'url' key it is used as-is, no further processing."""
        config = {
            "driver": "mysql",
            "url": "mysql+aiomysql://admin:pw@prod-host:3306/live",
            "host": "ignored",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "mysql+aiomysql://admin:pw@prod-host:3306/live")


class TestConnectionFactoryMissingPort(unittest.TestCase):
    """A missing/empty port must fall back to a sane per-driver default instead of
    producing a URL with a bare trailing colon that crashes at engine creation with
    `ValueError: invalid literal for int() with base 10: ''`."""

    def test_mysql_missing_port_uses_default_3306(self):
        config = {
            "driver": "mysql",
            "host": "localhost",
            "database": "mydb",
            "username": "root",
            "password": "secret",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "mysql+aiomysql://root:secret@localhost:3306/mydb")

    def test_postgres_missing_port_uses_default_5432(self):
        config = {
            "driver": "postgres",
            "host": "db.example.com",
            "database": "mydb",
            "username": "user",
            "password": "pass",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "postgresql+asyncpg://user:pass@db.example.com:5432/mydb")

    def test_mysql_empty_string_port_uses_default(self):
        config = {
            "driver": "mysql",
            "host": "localhost",
            "port": "",
            "database": "mydb",
            "username": "root",
            "password": "secret",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "mysql+aiomysql://root:secret@localhost:3306/mydb")

    def test_postgres_empty_string_port_uses_default(self):
        config = {
            "driver": "postgres",
            "host": "localhost",
            "port": "",
            "database": "mydb",
            "username": "user",
            "password": "pass",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "postgresql+asyncpg://user:pass@localhost:5432/mydb")

    def test_explicit_port_is_preserved(self):
        """An explicitly configured port must win over the default (happy path)."""
        config = {
            "driver": "postgres",
            "host": "localhost",
            "port": 6543,
            "database": "mydb",
            "username": "user",
            "password": "pass",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "postgresql+asyncpg://user:pass@localhost:6543/mydb")


class TestConnectionFactoryUnsupportedDriver(unittest.TestCase):
    """An unknown driver must raise a friendly framework error, not a raw KeyError."""

    def test_build_url_unknown_driver_raises_driver_not_found(self):
        with self.assertRaises(DriverNotFound) as ctx:
            ConnectionFactory.build_url({"driver": "oracle", "database": "mydb"})
        message = str(ctx.exception)
        self.assertIn("oracle", message)
        # The message should guide the user toward the supported drivers.
        self.assertIn("sqlite", message)
        self.assertIn("mysql", message)
        self.assertIn("postgres", message)

    def test_build_url_does_not_raise_raw_keyerror(self):
        with self.assertRaises(DriverNotFound):
            ConnectionFactory.build_url({"driver": "cassandra"})

    def test_make_unknown_driver_raises_driver_not_found(self):
        """make()'s driver check is reachable and fires before any engine is built."""
        with self.assertRaises(DriverNotFound):
            ConnectionFactory().make({"driver": "oracle", "database": "mydb"}, "oracle")

    def test_url_passthrough_bypasses_driver_validation(self):
        """The documented `url` stopgap short-circuits field assembly entirely, so an
        unknown driver name is irrelevant when a full url is supplied."""
        config = {
            "driver": "oracle",
            "url": "sqlite+aiosqlite:///db.sqlite3",
        }
        url = ConnectionFactory.build_url(config)
        self.assertEqual(url, "sqlite+aiosqlite:///db.sqlite3")

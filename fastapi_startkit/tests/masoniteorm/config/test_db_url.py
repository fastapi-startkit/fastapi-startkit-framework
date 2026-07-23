import unittest

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

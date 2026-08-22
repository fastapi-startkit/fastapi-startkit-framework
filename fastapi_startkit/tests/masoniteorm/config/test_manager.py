import tempfile
import unittest
from pathlib import Path

from fastapi_startkit.application import Application
from fastapi_startkit.exceptions.exceptions import DriverNotFound
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.providers import DatabaseProvider


class TestDatabaseManagerConnectionLookup(unittest.TestCase):
    """Regression test for GH issue #6.

    DatabaseProvider.register() binds the *full* resolved config (with
    top-level ``default``/``connections``/``migrations`` keys) into
    DatabaseManager, so connection() must look names up under the nested
    "connections" key rather than treating the whole config as a flat
    {connection_name: {...}} dict.
    """

    def test_connection_resolves_from_nested_connections_dict(self):
        config = {
            "default": "sqlite",
            "connections": {"sqlite": {"driver": "sqlite", "url": "sqlite+aiosqlite:///:memory:"}},
            "migrations": {"table": "migrations", "directory": "databases/migrations"},
        }
        manager = DatabaseManager(ConnectionFactory(), config)

        connection = manager.connection("sqlite")

        self.assertIsNotNone(connection)

    def test_default_connection_name_resolved_from_top_level_default(self):
        config = {
            "default": "sqlite",
            "connections": {"sqlite": {"driver": "sqlite", "url": "sqlite+aiosqlite:///:memory:"}},
            "migrations": {},
        }
        manager = DatabaseManager(ConnectionFactory(), config)

        connection = manager.connection()

        self.assertIsNotNone(connection)
        self.assertIn("sqlite", manager.connections)

    def test_missing_connection_raises_value_error_not_key_error(self):
        config = {"default": "sqlite", "connections": {}, "migrations": {}}
        manager = DatabaseManager(ConnectionFactory(), config)

        with self.assertRaises(ValueError):
            manager.connection("sqlite")


class TestDatabaseManagerBootTimeValidation(unittest.TestCase):
    """Task #1232: a misconfigured connection must fail loudly at
    construction (app-boot/provider-registration) time, not lazily on first
    use — building on top of PR #194's DriverNotFound exception.
    """

    def test_valid_configs_still_construct_without_error(self):
        """No behavior change for well-formed configs (sqlite/mysql/postgres)."""
        config = {
            "default": "sqlite",
            "connections": {
                "sqlite": {"driver": "sqlite", "database": "app.sqlite3"},
                "mysql": {"driver": "mysql", "host": "localhost", "database": "db"},
                "postgres": {"driver": "postgres", "host": "localhost", "port": 5432, "database": "db"},
            },
        }

        manager = DatabaseManager(ConnectionFactory(), config)

        self.assertIsInstance(manager, DatabaseManager)

    def test_missing_driver_key_raises_at_construction(self):
        config = {
            "default": "sqlite",
            "connections": {"sqlite": {"database": "app.sqlite3"}},
        }

        with self.assertRaises(DriverNotFound) as ctx:
            DatabaseManager(ConnectionFactory(), config)
        self.assertIn("sqlite", str(ctx.exception))

    def test_unsupported_driver_raises_at_construction(self):
        config = {
            "default": "mssql",
            "connections": {"mssql": {"driver": "mssql", "host": "localhost", "database": "db"}},
        }

        with self.assertRaises(DriverNotFound) as ctx:
            DatabaseManager(ConnectionFactory(), config)
        self.assertIn("mssql", str(ctx.exception))

    def test_non_numeric_port_raises_at_construction(self):
        config = {
            "default": "postgres",
            "connections": {
                "postgres": {"driver": "postgres", "host": "localhost", "port": "not-a-port", "database": "db"}
            },
        }

        with self.assertRaises(ValueError) as ctx:
            DatabaseManager(ConnectionFactory(), config)
        self.assertIn("port", str(ctx.exception))

    def test_missing_port_is_not_an_error(self):
        """Missing/empty port is not a misconfiguration -- ConnectionFactory
        fills in a per-driver default, so it must not fail validation."""
        config = {
            "default": "mysql",
            "connections": {"mysql": {"driver": "mysql", "host": "localhost", "database": "db"}},
        }

        manager = DatabaseManager(ConnectionFactory(), config)

        self.assertIsInstance(manager, DatabaseManager)

    def test_explicit_url_bypasses_driver_and_port_checks(self):
        """A connection configured entirely via `url` skips field validation,
        mirroring ConnectionFactory.build_url()'s own url passthrough."""
        config = {
            "default": "oracle",
            "connections": {"oracle": {"driver": "oracle", "url": "sqlite+aiosqlite:///:memory:"}},
        }

        manager = DatabaseManager(ConnectionFactory(), config)

        self.assertIsInstance(manager, DatabaseManager)

    def test_bad_connection_fails_at_provider_registration_not_first_query(self):
        """End-to-end: DatabaseProvider.register() runs during Application
        construction, so a bad config must raise while booting the app --
        before `db.connection()` is ever called."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DriverNotFound):
                Application(
                    base_path=Path(tmp),
                    env="testing",
                    providers=[
                        (
                            DatabaseProvider,
                            {
                                "default": "mssql",
                                "connections": {"mssql": {"driver": "mssql", "host": "localhost", "database": "db"}},
                            },
                        )
                    ],
                )


class TestDatabaseProviderWiring(unittest.TestCase):
    """DatabaseProvider.register() must produce a DatabaseManager whose
    connection() resolves cleanly — this is what `python artisan db:migrate`
    exercises on boot.
    """

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.base_path = Path(self._tmp_dir.name)

    def test_provider_wires_a_resolvable_connection(self):
        app = Application(
            base_path=self.base_path,
            env="testing",
            providers=[
                (
                    DatabaseProvider,
                    {
                        "default": "sqlite",
                        "connections": {
                            "sqlite": SQLiteConfig(driver="sqlite", url="sqlite+aiosqlite:///:memory:"),
                        },
                    },
                )
            ],
        )

        db = app.make("db")
        connection = db.connection()

        self.assertIsNotNone(connection)

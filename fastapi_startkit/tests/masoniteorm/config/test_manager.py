import tempfile
import unittest
from pathlib import Path

from fastapi_startkit.application import Application
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

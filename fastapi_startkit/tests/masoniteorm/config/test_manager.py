from fastapi_startkit.masoniteorm import DatabaseConfig, SQLiteConfig
import tempfile
import unittest
from pathlib import Path

from fastapi_startkit.application import Application
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.providers import DatabaseProvider


class TestDatabaseManagerConnectionLookup(unittest.TestCase):
    def test_connection_resolves_from_named_config_object(self):
        config = DatabaseConfig(
            default="sqlite",
            connections={"sqlite": SQLiteConfig(driver="sqlite", url="sqlite+aiosqlite:///:memory:")},
            migrations={"table": "migrations", "directory": "databases/migrations"},
        )
        manager = DatabaseManager(ConnectionFactory(), config)

        connection = manager.connection("sqlite")

        self.assertIsNotNone(connection)

    def test_default_connection_name_resolved_from_top_level_default(self):
        config = DatabaseConfig(
            default="sqlite",
            connections={"sqlite": SQLiteConfig(driver="sqlite", url="sqlite+aiosqlite:///:memory:")},
            migrations={},
        )
        manager = DatabaseManager(ConnectionFactory(), config)

        connection = manager.connection()

        self.assertIsNotNone(connection)
        self.assertIn("sqlite", manager.connections)

    def test_missing_connection_raises_value_error_not_key_error(self):
        config = DatabaseConfig(default="sqlite", connections={}, migrations={})
        manager = DatabaseManager(ConnectionFactory(), config)

        with self.assertRaises(ValueError):
            manager.connection("sqlite")


class TestDatabaseProviderWiring(unittest.TestCase):
    """DatabaseProvider.register() must produce a DatabaseManager whose
    connection() resolves cleanly — this is what `python artisan db:migrate`
    exercises on boot.
    """

    base_path: Path  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.base_path = Path(tmp_dir.name)

    def test_provider_wires_a_resolvable_connection(self):
        connection_config = SQLiteConfig(url="sqlite+aiosqlite:///:memory:")
        settings = DatabaseConfig(default="sqlite", connections={"sqlite": connection_config})
        app = Application(
            base_path=self.base_path,
            env="testing",
            providers=[
                (
                    DatabaseProvider,
                    settings,
                )
            ],
        )

        db = app.make("db")
        connection = db.connection()

        self.assertIsNotNone(connection)

        self.assertIs(db.config, settings)
        self.assertIs(connection.config, connection_config)

    def test_provider_rejects_dictionary_settings(self):
        with self.assertRaisesRegex(TypeError, "requires database settings; missing attributes: default, connections"):
            Application(
                base_path=self.base_path,
                env="testing",
                providers=[(DatabaseProvider, {"default": "sqlite"})],
            )

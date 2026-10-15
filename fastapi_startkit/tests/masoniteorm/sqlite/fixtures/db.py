from fastapi_startkit.masoniteorm import DatabaseConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.model import Model

DB = DatabaseManager(
    ConnectionFactory(),
    DatabaseConfig(
        default="sqlite",
        migrations={"directory": "fixtures/migrations"},
        connections={
            "sqlite": SQLiteConfig(driver="sqlite", url="sqlite+aiosqlite:///masonite.sqlite3"),
            "dev": SQLiteConfig(driver="sqlite", url="sqlite+aiosqlite:///masonite_dev.sqlite3"),
        },
    ),
)

Model.db_manager = DB

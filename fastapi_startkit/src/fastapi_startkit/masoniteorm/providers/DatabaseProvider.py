from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from fastapi_startkit.masoniteorm.commands import (
    DBMigrateCommand,
    DBSeedCommand,
    MakeMigrationCommand,
    MakeModelCommand,
    MakeObserverCommand,
    MakeSeedCommand,
    MigrateRollbackCommand,
    MigrateFreshCommand,
    MigrateRefreshCommand,
    MigrateStatusCommand,
)
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.config.config import DBConfig
from fastapi_startkit.masoniteorm.config.database import DatabaseConfig, DatabaseSettings
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator
from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.support import Provider
from fastapi_startkit.support.config import ensure_config
from fastapi_startkit.support.dataclass import Dataclass


def with_default_migrations(source: object) -> object:
    if hasattr(source, "migrations"):
        return source
    present = {name: getattr(source, name) for name in ("default", "connections") if hasattr(source, name)}
    return SimpleNamespace(**present, migrations=DatabaseConfig().migrations)


def settings_entry(source: object, settings: DatabaseSettings) -> dict[str, Any]:
    fields = Dataclass.to_dict(source)
    return {
        **Dataclass.to_dict(DatabaseConfig()),
        **(fields if isinstance(fields, dict) else {}),
        **Dataclass.to_dict(
            {
                "default": settings.default,
                "connections": dict(settings.connections),
                "migrations": dict(settings.migrations),
            }
        ),
    }


class DatabaseProvider(Provider):
    def register(self):
        source = cast(object, self.config) or DatabaseConfig()
        config = ensure_config("DatabaseProvider", with_default_migrations(source), DatabaseSettings)
        for name, connection in cast(Mapping[str, object], config.connections).items():
            if not isinstance(connection, DBConfig):
                raise TypeError(f"Database connection {name!r} requires a database config object")
        self.merge_config_from(settings_entry(source, config), self.provider_key)

        db = DatabaseManager(ConnectionFactory(), config)

        self.app.bind("db", db)
        self.app.bind("schema", db.get_schema_builder())

        Model.db_manager = db
        Migrator.db_manager = db

    def boot(self) -> None:
        self.publishes({Path(__file__).resolve().parent.parent.joinpath("config/database.py"): "config/database.py"})

        self.commands(
            [
                DBMigrateCommand,
                DBSeedCommand,
                MakeMigrationCommand,
                MigrateStatusCommand,
                MigrateRollbackCommand,
                MakeModelCommand,
                MakeObserverCommand,
                MakeSeedCommand,
                MigrateFreshCommand,
                MigrateRefreshCommand,
            ]
        )

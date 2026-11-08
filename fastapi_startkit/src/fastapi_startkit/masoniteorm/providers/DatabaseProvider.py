from pathlib import Path
from typing import cast

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
from fastapi_startkit.masoniteorm.config.database import DatabaseConfig, ensure_database_settings
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator
from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.support import Provider
from fastapi_startkit.support.config import ensure_config


class DatabaseProvider(Provider):
    def register(self):
        source = cast(object, self.config) or DatabaseConfig()
        ensure_config(source, "database")
        config = ensure_database_settings("DatabaseProvider", source)
        self.merge_config_from(self.resolve_config(DatabaseConfig), self.provider_key)

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

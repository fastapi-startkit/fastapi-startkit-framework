from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import cast

from fastapi_startkit.support.dataclass import Dataclass

from fastapi_startkit.masoniteorm.commands import (
    DBMigrateCommand,
    DBSeedCommand,
    MakeMigrationCommand,
    MakeModelCommand,
    MakeSeedCommand,
    MigrateRollbackCommand,
    MigrateFreshCommand,
    MigrateStatusCommand,
)
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm import Migrator
from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.support import Provider


class DatabaseProvider(Provider):
    def register(self):
        from ..config.config import DBConfig
        from ..config.database import DatabaseConfig

        source = cast(object, self.config)
        if not source:
            config = DatabaseConfig()
        elif isinstance(source, DatabaseConfig):
            config = source
        elif is_dataclass(source) and not isinstance(source, type):
            config = DatabaseConfig(**{field.name: getattr(source, field.name) for field in fields(source)})
        else:
            raise TypeError("DatabaseProvider requires a database settings dataclass")
        for name, connection in cast(dict[str, object], config.connections).items():
            if not isinstance(connection, DBConfig):
                raise TypeError(f"Database connection {name!r} requires a database config object")
        self.merge_config_from(Dataclass.to_dict(config), self.provider_key)

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
                MakeSeedCommand,
                MigrateFreshCommand,
            ]
        )

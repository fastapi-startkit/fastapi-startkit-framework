import datetime
from typing import Any

import pendulum
from sqlalchemy import event
from sqlalchemy.engine import Connection as SyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine

from fastapi_startkit.masoniteorm.config.config import DBConfig
from fastapi_startkit.masoniteorm.query.grammars import SQLiteGrammar
from fastapi_startkit.masoniteorm.query.processors import SQLitePostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import SQLitePlatform
from .connection import Connection


class SQliteConnection(Connection):
    def __init__(self, engine: AsyncEngine, config: DBConfig):
        super().__init__(engine, config)
        event.listen(engine.sync_engine, "savepoint", self.on_savepoint)

    @staticmethod
    def on_savepoint(connection: SyncConnection, name: str) -> None:
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")

    @classmethod
    def get_query_grammar(cls) -> type[SQLiteGrammar]:
        return SQLiteGrammar

    @classmethod
    def get_default_platform(cls):
        return SQLitePlatform

    @classmethod
    def get_post_processor(cls) -> type[SQLitePostProcessor]:
        return SQLitePostProcessor

    @classmethod
    def prepare_binding(cls, value: Any) -> Any:
        if isinstance(value, datetime.datetime):
            return pendulum.instance(value).in_timezone("UTC").naive().isoformat(sep=" ")
        if isinstance(value, datetime.date):
            return value.isoformat()
        return value

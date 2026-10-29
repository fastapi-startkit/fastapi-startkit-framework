import datetime
from pathlib import Path
from typing import Any

import pendulum
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from fastapi_startkit.masoniteorm.query.grammars import SQLiteGrammar
from fastapi_startkit.masoniteorm.query.processors import SQLitePostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import SQLitePlatform
from fastapi_startkit.masoniteorm.config.config import DBConfig
from .connection import Connection


class SQliteConnection(Connection):
    def __init__(self, engine: AsyncEngine, config: DBConfig):
        super().__init__(engine, config)
        if self.is_file_database(engine.url):
            Path(str(engine.url.database)).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_file_database(url: URL) -> bool:
        database = url.database
        return bool(database) and database != ":memory:" and not str(database).startswith("file:")

    @classmethod
    def resolve_url(cls, url: URL, base_path: Path) -> URL:
        if not cls.is_file_database(url) or Path(str(url.database)).is_absolute():
            return url
        return url.set(database=str(base_path / str(url.database)))

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

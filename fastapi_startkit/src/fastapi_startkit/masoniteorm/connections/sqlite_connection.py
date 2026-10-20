import datetime
from typing import Any

import pendulum

from fastapi_startkit.masoniteorm.query.grammars import SQLiteGrammar
from fastapi_startkit.masoniteorm.query.processors import SQLitePostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import SQLitePlatform
from .connection import Connection


class SQliteConnection(Connection):
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

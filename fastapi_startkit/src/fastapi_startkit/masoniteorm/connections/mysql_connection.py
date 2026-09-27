from fastapi_startkit.masoniteorm.query.grammars import MySQLGrammar
from fastapi_startkit.masoniteorm.query.processors import MySQLPostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import MySQLPlatform
from .connection import Connection


class MySQLConnection(Connection):
    """Async MySQL connection backed by aiomysql via SQLAlchemy."""

    @classmethod
    def get_query_grammar(cls) -> type[MySQLGrammar]:
        return MySQLGrammar

    @classmethod
    def get_default_platform(cls):
        return MySQLPlatform

    @classmethod
    def get_post_processor(cls) -> type[MySQLPostProcessor]:
        return MySQLPostProcessor

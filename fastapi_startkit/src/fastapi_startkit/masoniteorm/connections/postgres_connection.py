from fastapi_startkit.masoniteorm.query.grammars import PostgresGrammar
from fastapi_startkit.masoniteorm.query.processors import PostgresPostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform
from .connection import Connection


class PostgresConnection(Connection):
    """Async PostgreSQL connection backed by asyncpg via SQLAlchemy."""

    async def insert_get_id(self, query: str, bindings: list | None = None) -> int | None:
        result = await self.run(query, bindings)
        row = result.fetchone()
        return row[0] if row is not None else None

    @classmethod
    def get_query_grammar(cls):
        return PostgresGrammar

    @classmethod
    def get_default_platform(cls):
        return PostgresPlatform

    @classmethod
    def get_post_processor(cls):
        return PostgresPostProcessor

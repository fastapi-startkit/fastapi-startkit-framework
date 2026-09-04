from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from fastapi_startkit.masoniteorm.connections.postgres_connection import PostgresConnection
from fastapi_startkit.masoniteorm.query.grammars import PostgresGrammar
from fastapi_startkit.masoniteorm.query.processors import PostgresPostProcessor
from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform


class TestPostgresConnection(IsolatedAsyncioTestCase):
    @staticmethod
    def _connection_with_result(row):
        connection = PostgresConnection(engine=None, config={"driver": "postgres"})
        result = Mock()
        result.fetchone.return_value = row
        connection.run = AsyncMock(return_value=result)
        return connection

    async def test_insert_get_id_returns_first_column_of_returning_row(self):
        connection = self._connection_with_result((42,))
        inserted_id = await connection.insert_get_id(
            "INSERT INTO users (name) VALUES (?) RETURNING id", ["Joe"]
        )
        self.assertEqual(inserted_id, 42)

    async def test_insert_get_id_returns_none_when_no_row(self):
        connection = self._connection_with_result(None)
        inserted_id = await connection.insert_get_id(
            "INSERT INTO users (name) VALUES (?) RETURNING id", ["Joe"]
        )
        self.assertIsNone(inserted_id)

    def test_grammar_platform_and_processor_classes(self):
        self.assertIs(PostgresConnection.get_query_grammar(), PostgresGrammar)
        self.assertIs(PostgresConnection.get_default_platform(), PostgresPlatform)
        self.assertIs(PostgresConnection.get_post_processor(), PostgresPostProcessor)

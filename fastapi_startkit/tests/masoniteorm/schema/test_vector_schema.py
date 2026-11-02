import unittest
from unittest.mock import AsyncMock, MagicMock

from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint
from fastapi_startkit.masoniteorm.schema.platforms import MSSQLPlatform, MySQLPlatform, PostgresPlatform, SQLitePlatform
from fastapi_startkit.masoniteorm.schema.schema import Schema
from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff

NON_POSTGRES_PLATFORMS = (SQLitePlatform, MySQLPlatform, MSSQLPlatform)


def blueprint(table, platform=PostgresPlatform):
    return Blueprint(grammar=None, table=table, platform=platform, dry=True)


class TestVectorSchema(unittest.TestCase):
    def test_vector_column_renders_with_dimensions(self):
        table = Table("documents")
        blueprint(table).vector("embedding", dimensions=1536)

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table),
            ['CREATE TABLE "documents" ("embedding" VECTOR(1536) NOT NULL)'],
        )

    def test_nullable_vector_column(self):
        table = Table("documents")
        blueprint(table).vector("embedding", dimensions=3, nullable=True)

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table), ['CREATE TABLE "documents" ("embedding" VECTOR(3) NULL)']
        )

    def test_index_on_a_vector_column_creates_an_hnsw_cosine_index(self):
        table = Table("documents")
        blueprint(table).vector("embedding", dimensions=1536).index()

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table)[1],
            'CREATE INDEX documents_embedding_index ON "documents" USING hnsw (embedding vector_cosine_ops)',
        )

    def test_index_on_other_columns_stays_a_btree_index(self):
        table = Table("documents")
        blueprint(table).string("title").index()

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table)[1], 'CREATE INDEX documents_title_index ON "documents"(title)'
        )

    def test_adding_an_indexed_vector_column_to_an_existing_table(self):
        table = TableDiff("documents")
        blueprint(table).vector("embedding", dimensions=8).index("embedding")
        blueprint(table).vector("summary_embedding", dimensions=8).index()

        self.assertEqual(
            PostgresPlatform().compile_alter_sql(table),
            [
                'ALTER TABLE "documents" ADD COLUMN "embedding" VECTOR(8) NOT NULL, '
                'ADD COLUMN "summary_embedding" VECTOR(8) NOT NULL',
                'CREATE INDEX documents_embedding_index ON "documents" USING hnsw (embedding vector_cosine_ops)',
                'CREATE INDEX documents_summary_embedding_index ON "documents" '
                "USING hnsw (summary_embedding vector_cosine_ops)",
            ],
        )

    def test_named_index_on_a_vector_column_creates_an_hnsw_index(self):
        table = Table("documents")
        blueprint(table).vector("embedding", dimensions=1536).string("title")
        blueprint(table).index("embedding", name="documents_embedding_hnsw")

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table)[1],
            'CREATE INDEX documents_embedding_hnsw ON "documents" USING hnsw (embedding vector_cosine_ops)',
        )

    def test_named_index_on_a_regular_column_stays_a_btree_index(self):
        table = Table("documents")
        blueprint(table).vector("embedding", dimensions=3).string("title")
        blueprint(table).index("title")

        self.assertEqual(
            PostgresPlatform().compile_create_sql(table)[1], 'CREATE INDEX documents_title_index ON "documents"(title)'
        )

    def test_vector_index_on_an_existing_column(self):
        table = TableDiff("documents")
        blueprint(table).vector_index("embedding")

        self.assertEqual(
            PostgresPlatform().compile_alter_sql(table),
            ['CREATE INDEX documents_embedding_index ON "documents" USING hnsw (embedding vector_cosine_ops)'],
        )

    def test_vector_indexes_require_postgres(self):
        for platform in NON_POSTGRES_PLATFORMS:
            with self.subTest(platform=platform.__name__):
                with self.assertRaisesRegex(ValueError, "does not support vector indexes"):
                    blueprint(Table("documents"), platform).vector_index("embedding")

    def test_vector_columns_require_postgres(self):
        for platform in NON_POSTGRES_PLATFORMS:
            with self.subTest(platform=platform.__name__):
                with self.assertRaisesRegex(ValueError, "does not support vector columns"):
                    blueprint(Table("documents"), platform).vector("embedding", dimensions=3)

    def test_postgres_compiles_the_vector_extension(self):
        self.assertEqual(PostgresPlatform().compile_ensure_vector_extension(), "CREATE EXTENSION IF NOT EXISTS vector")

    def test_other_platforms_reject_the_vector_extension(self):
        for platform in NON_POSTGRES_PLATFORMS:
            with self.subTest(platform=platform.__name__):
                with self.assertRaisesRegex(ValueError, "does not support vector columns"):
                    platform().compile_ensure_vector_extension()


class TestSchemaVectorExtension(unittest.IsolatedAsyncioTestCase):
    async def test_schema_ensures_the_vector_extension(self):
        connection = MagicMock()
        connection.get_default_platform.return_value = PostgresPlatform
        connection.statement = AsyncMock()
        manager = MagicMock()
        manager.connection.return_value = connection

        await Schema(manager).ensure_vector_extension_exists()

        connection.statement.assert_awaited_once_with("CREATE EXTENSION IF NOT EXISTS vector", ())

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint
from fastapi_startkit.masoniteorm.schema.platforms import MSSQLPlatform, MySQLPlatform, PostgresPlatform, SQLitePlatform
from fastapi_startkit.masoniteorm.schema.schema import Schema
from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff


def blueprint(table, platform=PostgresPlatform):
    return Blueprint(grammar=None, table=table, platform=platform, dry=True)


def test_vector_column_renders_with_dimensions():
    table = Table("documents")
    blueprint(table).vector("embedding", dimensions=1536)

    assert PostgresPlatform().compile_create_sql(table) == [
        'CREATE TABLE "documents" ("embedding" VECTOR(1536) NOT NULL)'
    ]


def test_nullable_vector_column():
    table = Table("documents")
    blueprint(table).vector("embedding", dimensions=3, nullable=True)

    assert PostgresPlatform().compile_create_sql(table) == ['CREATE TABLE "documents" ("embedding" VECTOR(3) NULL)']


def test_index_on_a_vector_column_creates_an_hnsw_cosine_index():
    table = Table("documents")
    blueprint(table).vector("embedding", dimensions=1536).index()

    assert PostgresPlatform().compile_create_sql(table)[1] == (
        'CREATE INDEX documents_embedding_index ON "documents" USING hnsw (embedding vector_cosine_ops)'
    )


def test_index_on_other_columns_stays_a_btree_index():
    table = Table("documents")
    blueprint(table).string("title").index()

    assert PostgresPlatform().compile_create_sql(table)[1] == (
        'CREATE INDEX documents_title_index ON "documents"(title)'
    )


def test_adding_an_indexed_vector_column_to_an_existing_table():
    table = TableDiff("documents")
    blueprint(table).vector("embedding", dimensions=8).index("embedding")
    blueprint(table).vector("summary_embedding", dimensions=8).index()

    assert PostgresPlatform().compile_alter_sql(table) == [
        'ALTER TABLE "documents" ADD COLUMN "embedding" VECTOR(8) NOT NULL, '
        'ADD COLUMN "summary_embedding" VECTOR(8) NOT NULL',
        'CREATE INDEX documents_embedding_index ON "documents"(embedding)',
        'CREATE INDEX documents_summary_embedding_index ON "documents" USING hnsw (summary_embedding vector_cosine_ops)',
    ]


@pytest.mark.parametrize("platform", [SQLitePlatform, MySQLPlatform, MSSQLPlatform])
def test_vector_columns_require_postgres(platform):
    with pytest.raises(ValueError, match="does not support vector columns"):
        blueprint(Table("documents"), platform).vector("embedding", dimensions=3)


def test_postgres_compiles_the_vector_extension():
    assert PostgresPlatform().compile_ensure_vector_extension() == "CREATE EXTENSION IF NOT EXISTS vector"


@pytest.mark.parametrize("platform", [SQLitePlatform, MySQLPlatform, MSSQLPlatform])
def test_other_platforms_reject_the_vector_extension(platform):
    with pytest.raises(ValueError, match="does not support vector columns"):
        platform().compile_ensure_vector_extension()


async def test_schema_ensures_the_vector_extension():
    connection = MagicMock()
    connection.get_default_platform.return_value = PostgresPlatform
    connection.statement = AsyncMock()
    manager = MagicMock()
    manager.connection.return_value = connection

    await Schema(manager).ensure_vector_extension_exists()

    connection.statement.assert_awaited_once_with("CREATE EXTENSION IF NOT EXISTS vector", ())

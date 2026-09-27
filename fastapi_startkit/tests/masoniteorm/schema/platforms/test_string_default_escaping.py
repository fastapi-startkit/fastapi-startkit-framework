import pytest

from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff
from fastapi_startkit.masoniteorm.schema.platforms import (
    MSSQLPlatform,
    MySQLPlatform,
    PostgresPlatform,
    SQLitePlatform,
)
from fastapi_startkit.masoniteorm.schema.platforms.Platform import Platform

PLATFORMS = [SQLitePlatform, MySQLPlatform, PostgresPlatform, MSSQLPlatform]


class MinimalPlatform(Platform):
    type_map = {"string": "VARCHAR"}
    premapped_defaults = {}
    premapped_nulls = {True: "NULL", False: "NOT NULL"}

    def columnize_string(self) -> str:
        return "{name} {data_type}{length} {nullable}{default} {constraint}"


def test_quote_string_doubles_single_quotes():
    assert Platform.quote_string("it's") == "'it''s'"
    assert Platform.quote_string("plain") == "'plain'"


@pytest.mark.parametrize("platform_class", PLATFORMS)
def test_create_escapes_quotes_in_string_defaults(platform_class):
    table = Table("notes")
    table.add_column("title", "string", length=50, default="it's")

    sql = platform_class().compile_create_sql(table)[0]

    assert "DEFAULT 'it''s'" in sql


@pytest.mark.parametrize("platform_class", PLATFORMS)
def test_alter_add_column_escapes_quotes_in_string_defaults(platform_class):
    diff = TableDiff("notes")
    diff.add_column("title", "string", default="it's")

    sql = platform_class().compile_alter_sql(diff)

    assert "DEFAULT 'it''s'" in " ".join(sql)


def test_base_columnize_escapes_quotes_in_string_defaults():
    table = Table("notes")
    table.add_column("title", "string", default="it's")

    assert "DEFAULT 'it''s'" in MinimalPlatform().columnize(table.get_added_columns())[0]

import unittest

from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff
from fastapi_startkit.masoniteorm.schema.platforms import (
    MSSQLPlatform,
    MySQLPlatform,
    PostgresPlatform,
    SQLitePlatform,
)

QUOTED_KEY_BY_PLATFORM = {
    MySQLPlatform: "`key`",
    PostgresPlatform: '"key"',
    SQLitePlatform: '"key"',
    MSSQLPlatform: "[key]",
}


def caches_table():
    table = Table("caches")
    table.add_column("key", "string", length=255)
    return table


class TestReservedWordColumns(unittest.TestCase):
    def assert_key_is_quoted(self, statements, quoted_key):
        sql = " ".join(statements) if isinstance(statements, list) else statements
        self.assertIn(f"({quoted_key})", sql)
        self.assertNotIn("(key)", sql)

    def test_create_quotes_a_primary_key_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                table = caches_table()
                table.add_constraint("caches_key_primary", "primary_key", columns=["key"])
                self.assert_key_is_quoted(platform().compile_create_sql(table), quoted_key)

    def test_create_quotes_a_unique_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                table = caches_table()
                table.add_constraint("caches_key_unique", "unique", columns=["key"])
                self.assert_key_is_quoted(platform().compile_create_sql(table), quoted_key)

    def test_create_quotes_an_index_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                table = caches_table()
                table.add_index(["key"], "caches_key_index", "index")
                self.assert_key_is_quoted(platform().compile_create_sql(table), quoted_key)

    def test_alter_quotes_a_primary_key_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                diff = TableDiff("caches")
                diff.add_constraint("caches_key_primary", "primary_key", columns=["key"])
                self.assert_key_is_quoted(platform().compile_alter_sql(diff), quoted_key)

    def test_alter_quotes_a_unique_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                diff = TableDiff("caches")
                diff.add_constraint("caches_key_unique", "unique", columns=["key"])
                self.assert_key_is_quoted(platform().compile_alter_sql(diff), quoted_key)

    def test_alter_quotes_an_index_column(self):
        for platform, quoted_key in QUOTED_KEY_BY_PLATFORM.items():
            with self.subTest(platform=platform.__name__):
                diff = TableDiff("caches")
                diff.add_index(["key"], "caches_key_index", "index")
                self.assert_key_is_quoted(platform().compile_alter_sql(diff), quoted_key)

    def test_mysql_alter_quotes_a_fulltext_column(self):
        diff = TableDiff("caches")
        diff.add_constraint("caches_key_fulltext", "fulltext", columns=["key"])
        self.assert_key_is_quoted(MySQLPlatform().compile_alter_sql(diff), "`key`")

    def test_composite_columns_keep_their_order(self):
        table = caches_table()
        table.add_column("order", "integer")
        table.add_constraint("caches_key_order_primary", "primary_key", columns=["key", "order"])
        self.assertIn("PRIMARY KEY (`key`, `order`)", MySQLPlatform().compile_create_sql(table)[0])

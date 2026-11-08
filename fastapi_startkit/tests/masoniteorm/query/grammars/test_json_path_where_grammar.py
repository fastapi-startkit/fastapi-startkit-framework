import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar


def builder(grammar):
    query = QueryBuilder(connection=None, grammar=grammar, processor=None)
    query._table = "posts"
    return query


class TestJsonPathColumnGrammar(unittest.TestCase):
    def test_postgres_reads_the_last_key_as_text(self):
        sql = PostgresGrammar(table="posts")._table_column_string("settings->headline")
        self.assertEqual(sql, '"posts"."settings"->>\'headline\'')

    def test_postgres_walks_nested_keys_as_json(self):
        sql = PostgresGrammar(table="posts")._table_column_string("settings->meta->headline")
        self.assertEqual(sql, "\"posts\".\"settings\"->'meta'->>'headline'")

    def test_sqlite_extracts_the_path(self):
        sql = SQLiteGrammar(table="posts")._table_column_string("settings->meta->headline")
        self.assertEqual(sql, 'json_extract("posts"."settings", \'$."meta"."headline"\')')

    def test_mysql_unquotes_the_extracted_path(self):
        sql = MySQLGrammar(table="posts")._table_column_string("settings->headline")
        self.assertEqual(sql, "json_unquote(json_extract(`posts`.`settings`, '$.\"headline\"'))")

    def test_mssql_reads_the_scalar_value(self):
        sql = MSSQLGrammar(table="posts")._table_column_string("settings->headline")
        self.assertEqual(sql, "json_value([posts].[settings], '$.\"headline\"')")

    def test_table_prefix_applies_to_the_column(self):
        sql = PostgresGrammar(table="posts")._table_column_string("drafts.settings->headline")
        self.assertEqual(sql, '"drafts"."settings"->>\'headline\'')

    def test_alias_and_separator_follow_the_expression(self):
        sql = PostgresGrammar(table="posts")._table_column_string(
            "settings->headline", alias="headline", separator=", "
        )
        self.assertEqual(sql, '"posts"."settings"->>\'headline\' AS headline, ')

    def test_keys_outside_word_characters_are_rejected(self):
        for key in ["head'line", "head line", "", 'head"line']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                PostgresGrammar(table="posts")._table_column_string(f"settings->{key}")


class TestJsonPathWhereGrammar(unittest.TestCase):
    def test_postgres_where_binds_the_value(self):
        query = builder(PostgresGrammar).where("settings->headline", "like", "%Paris%")
        sql = query.to_qmark()
        self.assertIn('WHERE "posts"."settings"->>\'headline\' ILIKE ', sql)
        self.assertNotIn("Paris", sql)
        self.assertEqual(list(query.get_bindings()), ["%Paris%"])

    def test_sqlite_or_where_binds_the_value(self):
        query = (
            builder(SQLiteGrammar).where("title", "like", "%Paris%").or_where("settings->headline", "like", "%Rome%")
        )
        sql = query.to_qmark()
        self.assertIn(' OR json_extract("posts"."settings", \'$."headline"\') LIKE ', sql)
        self.assertNotIn("Rome", sql)
        self.assertEqual(list(query.get_bindings()), ["%Paris%", "%Rome%"])

    def test_order_by_a_json_path(self):
        sql = builder(PostgresGrammar).order_by("settings->headline").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "posts" ORDER BY "posts"."settings"->>\'headline\' ASC')

    def test_union_members_compile_json_paths(self):
        pages = builder(PostgresGrammar).select("id").where("meta->seo->title", "Rome")
        pages._table = "pages"
        query = builder(PostgresGrammar).select("id").where("settings->headline", "Paris").union_all(pages)
        self.assertEqual(
            query.to_qmark(),
            '(SELECT "posts"."id" FROM "posts" WHERE "posts"."settings"->>\'headline\' = ?) UNION ALL '
            '(SELECT "pages"."id" FROM "pages" WHERE "pages"."meta"->\'seo\'->>\'title\' = ?)',
        )
        self.assertEqual(list(query.get_bindings()), ["Paris", "Rome"])

    def test_from_sub_compiles_json_paths_inside_and_outside(self):
        subquery = builder(SQLiteGrammar).select("id", "settings").where("settings->headline", "Paris")
        query = builder(SQLiteGrammar).from_sub(subquery, "events").where("events.settings->lang", "fr")
        self.assertEqual(
            query.to_qmark(),
            'SELECT * FROM (SELECT "posts"."id", "posts"."settings" FROM "posts" '
            'WHERE json_extract("posts"."settings", \'$."headline"\') = ?) AS "events" '
            'WHERE json_extract("events"."settings", \'$."lang"\') = ?',
        )
        self.assertEqual(list(query.get_bindings()), ["Paris", "fr"])

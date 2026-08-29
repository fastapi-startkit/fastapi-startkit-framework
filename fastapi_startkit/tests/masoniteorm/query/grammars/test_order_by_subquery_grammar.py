import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar

GRAMMARS = {
    "sqlite": SQLiteGrammar,
    "mysql": MySQLGrammar,
    "postgres": PostgresGrammar,
    "mssql": MSSQLGrammar,
}

EXPECTED = {
    "sqlite": {
        "sql": 'SELECT * FROM "posts" ORDER BY (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id) ASC',
        "qmark": 'SELECT * FROM "posts" WHERE "posts"."status" = ? ORDER BY (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id AND "categories"."active" = ?) ASC',
    },
    "mysql": {
        "sql": "SELECT * FROM `posts` ORDER BY (SELECT `categories`.`name` FROM `categories` WHERE categories.id = posts.category_id) ASC",
        "qmark": "SELECT * FROM `posts` WHERE `posts`.`status` = ? ORDER BY (SELECT `categories`.`name` FROM `categories` WHERE categories.id = posts.category_id AND `categories`.`active` = ?) ASC",
    },
    "postgres": {
        "sql": 'SELECT * FROM "posts" ORDER BY (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id) ASC',
        "qmark": 'SELECT * FROM "posts" WHERE "posts"."status" = ? ORDER BY (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id AND "categories"."active" = ?) ASC',
    },
    "mssql": {
        "sql": "SELECT * FROM [posts] ORDER BY (SELECT [categories].[name] FROM [categories] WHERE categories.id = posts.category_id) ASC",
        "qmark": "SELECT * FROM [posts] WHERE [posts].[status] = ? ORDER BY (SELECT [categories].[name] FROM [categories] WHERE categories.id = posts.category_id AND [categories].[active] = ?) ASC",
    },
}


def qb(grammar, table):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


def category_subquery(grammar):
    return qb(grammar, "categories").select("name").where_column("categories.id", "posts.category_id")


class TestOrderBySubqueryGrammar(unittest.TestCase):
    """Grammar-level parity for order_by() with a correlated-subquery builder."""

    def test_order_by_builder(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").order_by(category_subquery(grammar)).to_sql()
                self.assertEqual(sql, EXPECTED[name]["sql"])

    def test_order_by_builder_desc(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").order_by(category_subquery(grammar), "desc").to_sql()
                self.assertTrue(sql.endswith(") DESC"))

    def test_order_by_builder_qmark_and_binding_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar, "posts")
                    .where("posts.status", "active")
                    .order_by(
                        qb(grammar, "categories")
                        .select("name")
                        .where_column("categories.id", "posts.category_id")
                        .where("categories.active", 1)
                    )
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["qmark"])
                # WHERE binding precedes the ORDER BY subquery binding.
                self.assertEqual(list(q.get_bindings()), ["active", 1])

    def test_string_order_by_unchanged(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").order_by("id", "desc").to_sql()
                self.assertTrue(sql.endswith('"id" DESC') or sql.endswith("`id` DESC") or sql.endswith("[id] DESC"))


if __name__ == "__main__":
    unittest.main()

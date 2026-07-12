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
        "select_sub": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat_name FROM "posts"',
        "variadic": 'SELECT "posts"."id", "posts"."title", "posts"."category_id" FROM "posts"',
        "assoc_empty": 'SELECT "posts".*, (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM "posts"',
        "assoc_after_select": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM "posts"',
        "select_sub_qmark": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE "categories"."active" = ? LIMIT 1) AS cat FROM "posts" WHERE "posts"."status" = ?',
    },
    "mysql": {
        "select_sub": "SELECT `posts`.`id`, (SELECT `categories`.`name` FROM `categories` WHERE categories.id = posts.category_id LIMIT 1) AS cat_name FROM `posts`",
        "variadic": "SELECT `posts`.`id`, `posts`.`title`, `posts`.`category_id` FROM `posts`",
        "assoc_empty": "SELECT `posts`.*, (SELECT `categories`.`name` FROM `categories` WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM `posts`",
        "assoc_after_select": "SELECT `posts`.`id`, (SELECT `categories`.`name` FROM `categories` WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM `posts`",
        "select_sub_qmark": "SELECT `posts`.`id`, (SELECT `categories`.`name` FROM `categories` WHERE `categories`.`active` = ? LIMIT 1) AS cat FROM `posts` WHERE `posts`.`status` = ?",
    },
    "postgres": {
        "select_sub": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat_name FROM "posts"',
        "variadic": 'SELECT "posts"."id", "posts"."title", "posts"."category_id" FROM "posts"',
        "assoc_empty": 'SELECT "posts".*, (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM "posts"',
        "assoc_after_select": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE categories.id = posts.category_id LIMIT 1) AS cat FROM "posts"',
        "select_sub_qmark": 'SELECT "posts"."id", (SELECT "categories"."name" FROM "categories" WHERE "categories"."active" = ? LIMIT 1) AS cat FROM "posts" WHERE "posts"."status" = ?',
    },
    "mssql": {
        "select_sub": "SELECT [posts].[id], (SELECT TOP 1 [categories].[name] FROM [categories] WHERE categories.id = posts.category_id) AS cat_name FROM [posts]",
        "variadic": "SELECT [posts].[id], [posts].[title], [posts].[category_id] FROM [posts]",
        "assoc_empty": "SELECT [posts].*, (SELECT TOP 1 [categories].[name] FROM [categories] WHERE categories.id = posts.category_id) AS cat FROM [posts]",
        "assoc_after_select": "SELECT [posts].[id], (SELECT TOP 1 [categories].[name] FROM [categories] WHERE categories.id = posts.category_id) AS cat FROM [posts]",
        "select_sub_qmark": "SELECT [posts].[id], (SELECT TOP 1 [categories].[name] FROM [categories] WHERE [categories].[active] = ?) AS cat FROM [posts] WHERE [posts].[status] = ?",
    },
}


def qb(grammar, table):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


def category_subquery(grammar):
    return qb(grammar, "categories").select("name").where_column("categories.id", "posts.category_id").limit(1)


class TestSelectSubGrammar(unittest.TestCase):
    """Grammar-level parity for select_sub (subquery-as-column) across all dialects."""

    def test_select_sub_builder(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").select("id").select_sub(category_subquery(grammar), "cat_name").to_sql()
                self.assertEqual(sql, EXPECTED[name]["select_sub"])

    def test_select_sub_callable(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = (
                    qb(grammar, "posts")
                    .select("id")
                    .select_sub(
                        lambda q: (
                            q.table("categories")
                            .select("name")
                            .where_column("categories.id", "posts.category_id")
                            .limit(1)
                        ),
                        "cat_name",
                    )
                    .to_sql()
                )
                self.assertEqual(sql, EXPECTED[name]["select_sub"])

    def test_select_sub_rejects_non_builder(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                with self.assertRaises(TypeError):
                    qb(grammar, "posts").select_sub("not-a-builder", "cat")

    def test_select_sub_qmark_binding_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sub = qb(grammar, "categories").select("name").where("categories.active", 1).limit(1)
                q = qb(grammar, "posts").select("id").select_sub(sub, "cat").where("posts.status", "active")
                self.assertEqual(q.to_qmark(), EXPECTED[name]["select_sub_qmark"])
                # SELECT-clause subquery binding precedes the WHERE binding.
                self.assertEqual(list(q.get_bindings()), [1, "active"])


class TestAddSelectGrammar(unittest.TestCase):
    """add_select() is Laravel's variadic column-adder, not a subquery method."""

    def test_add_select_variadic_strings(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").select("id").add_select("title", "category_id").to_sql()
                self.assertEqual(sql, EXPECTED[name]["variadic"])

    def test_add_select_single_list(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").select("id").add_select(["title", "category_id"]).to_sql()
                self.assertEqual(sql, EXPECTED[name]["variadic"])

    def test_add_select_dedup_guard(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                # 'title' already selected -> not duplicated
                sql = qb(grammar, "posts").select("id", "title").add_select("title", "category_id").to_sql()
                self.assertEqual(sql, EXPECTED[name]["variadic"])

    def test_add_select_assoc_seeds_table_star_when_empty(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").add_select({"cat": category_subquery(grammar)}).to_sql()
                self.assertEqual(sql, EXPECTED[name]["assoc_empty"])

    def test_add_select_assoc_keeps_existing_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").select("id").add_select({"cat": category_subquery(grammar)}).to_sql()
                self.assertEqual(sql, EXPECTED[name]["assoc_after_select"])

    def test_add_select_assoc_callable(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = (
                    qb(grammar, "posts")
                    .add_select(
                        {
                            "cat": lambda q: (
                                q.table("categories")
                                .select("name")
                                .where_column("categories.id", "posts.category_id")
                                .limit(1)
                            )
                        }
                    )
                    .to_sql()
                )
                self.assertEqual(sql, EXPECTED[name]["assoc_empty"])

    def test_add_select_string_value_under_string_key_is_plain_column(self):
        # Laravel: only string-key + queryable-value delegates; a string value stays a column.
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").select("id").add_select({"ignored_key": "title"}).to_sql()
                plain = qb(grammar, "posts").select("id").add_select("title").to_sql()
                self.assertEqual(sql, plain)

    def test_add_select_list_mixed_columns_and_subquery(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar, "posts").add_select(["id", {"cat": category_subquery(grammar)}]).to_sql()
                self.assertIn("AS cat", sql)
                # both the plain column and the subquery column are present
                self.assertIn("id", sql)

    def test_add_select_bare_subquery_without_alias_raises(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                with self.assertRaises(TypeError):
                    qb(grammar, "posts").add_select(qb(grammar, "categories").select("name"))

    def test_add_select_assoc_qmark_binding_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sub = qb(grammar, "categories").select("name").where("categories.active", 1).limit(1)
                q = qb(grammar, "posts").select("id").add_select({"cat": sub}).where("posts.status", "active")
                self.assertEqual(q.to_qmark(), EXPECTED[name]["select_sub_qmark"])
                self.assertEqual(list(q.get_bindings()), [1, "active"])


if __name__ == "__main__":
    unittest.main()

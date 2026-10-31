import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar

GRAMMARS = {
    "sqlite": SQLiteGrammar,
    "mysql": MySQLGrammar,
    "postgres": PostgresGrammar,
    "mssql": MSSQLGrammar,
}

EXPECTED = {
    "sqlite": {
        "cte": 'WITH "totals" AS (SELECT "orders"."user_id", sum(amount) as total FROM "orders" WHERE "orders"."status" = ? GROUP BY "orders"."user_id") SELECT * FROM "users" INNER JOIN "totals" ON "totals"."user_id" = "users"."id" WHERE "users"."active" = ?',
        "multi": 'WITH "a" AS (SELECT * FROM "orders" WHERE "orders"."x" = ?), "b" AS (SELECT * FROM "a" WHERE "a"."y" = ?) SELECT * FROM "b" WHERE "b"."z" = ?',
        "from_sub": 'SELECT * FROM (SELECT "orders"."user_id", count(*) as n FROM "orders" WHERE "orders"."status" = ? GROUP BY "orders"."user_id") AS "t" WHERE "t"."n" > ?',
        "add_select_raw": 'SELECT "t".*, t.amount * ? as taxed FROM (SELECT * FROM "orders") AS "t"',
        "combined": 'WITH "recent" AS (SELECT * FROM "orders" WHERE "orders"."created_at" >= ?) SELECT "w"."user_id", max(w.weighted) + ? as top FROM (SELECT "orders"."user_id", sum(amount) * ? as weighted FROM "orders" WHERE "orders"."amount" > ? GROUP BY "orders"."user_id") AS "w" INNER JOIN "users" ON "users"."id" = "w"."user_id" WHERE "users"."active" = ? GROUP BY "w"."user_id" HAVING count(*) > ? ORDER BY "w"."user_id" ASC LIMIT 10 OFFSET 20',
    },
    "mysql": {
        "cte": "WITH `totals` AS (SELECT `orders`.`user_id`, sum(amount) as total FROM `orders` WHERE `orders`.`status` = ? GROUP BY `orders`.`user_id`) SELECT * FROM `users` INNER JOIN `totals` ON `totals`.`user_id` = `users`.`id` WHERE `users`.`active` = ?",
        "multi": "WITH `a` AS (SELECT * FROM `orders` WHERE `orders`.`x` = ?), `b` AS (SELECT * FROM `a` WHERE `a`.`y` = ?) SELECT * FROM `b` WHERE `b`.`z` = ?",
        "from_sub": "SELECT * FROM (SELECT `orders`.`user_id`, count(*) as n FROM `orders` WHERE `orders`.`status` = ? GROUP BY `orders`.`user_id`) AS `t` WHERE `t`.`n` > ?",
        "add_select_raw": "SELECT `t`.*, t.amount * ? as taxed FROM (SELECT * FROM `orders`) AS `t`",
        "combined": "WITH `recent` AS (SELECT * FROM `orders` WHERE `orders`.`created_at` >= ?) SELECT `w`.`user_id`, max(w.weighted) + ? as top FROM (SELECT `orders`.`user_id`, sum(amount) * ? as weighted FROM `orders` WHERE `orders`.`amount` > ? GROUP BY `orders`.`user_id`) AS `w` INNER JOIN `users` ON `users`.`id` = `w`.`user_id` WHERE `users`.`active` = ? GROUP BY `w`.`user_id` HAVING count(*) > ? ORDER BY `w`.`user_id` ASC LIMIT 10 OFFSET 20",
    },
    "postgres": {
        "cte": 'WITH "totals" AS (SELECT "orders"."user_id", sum(amount) as total FROM "orders" WHERE "orders"."status" = ? GROUP BY "orders"."user_id") SELECT * FROM "users" INNER JOIN "totals" ON "totals"."user_id" = "users"."id" WHERE "users"."active" = ?',
        "multi": 'WITH "a" AS (SELECT * FROM "orders" WHERE "orders"."x" = ?), "b" AS (SELECT * FROM "a" WHERE "a"."y" = ?) SELECT * FROM "b" WHERE "b"."z" = ?',
        "from_sub": 'SELECT * FROM (SELECT "orders"."user_id", count(*) as n FROM "orders" WHERE "orders"."status" = ? GROUP BY "orders"."user_id") AS "t" WHERE "t"."n" > ?',
        "add_select_raw": 'SELECT "t".*, t.amount * ? as taxed FROM (SELECT * FROM "orders") AS "t"',
        "combined": 'WITH "recent" AS (SELECT * FROM "orders" WHERE "orders"."created_at" >= ?) SELECT "w"."user_id", max(w.weighted) + ? as top FROM (SELECT "orders"."user_id", sum(amount) * ? as weighted FROM "orders" WHERE "orders"."amount" > ? GROUP BY "orders"."user_id") AS "w" INNER JOIN "users" ON "users"."id" = "w"."user_id" WHERE "users"."active" = ? GROUP BY "w"."user_id" HAVING count(*) > ? ORDER BY "w"."user_id" ASC LIMIT 10 OFFSET 20',
    },
    "mssql": {
        "cte": "WITH [totals] AS (SELECT [orders].[user_id], sum(amount) as total FROM [orders] WHERE [orders].[status] = ? GROUP BY [orders].[user_id]) SELECT * FROM [users] INNER JOIN [totals] ON [totals].[user_id] = [users].[id] WHERE [users].[active] = ?",
        "multi": "WITH [a] AS (SELECT * FROM [orders] WHERE [orders].[x] = ?), [b] AS (SELECT * FROM [a] WHERE [a].[y] = ?) SELECT * FROM [b] WHERE [b].[z] = ?",
        "from_sub": "SELECT * FROM (SELECT [orders].[user_id], count(*) as n FROM [orders] WHERE [orders].[status] = ? GROUP BY [orders].[user_id]) AS [t] WHERE [t].[n] > ?",
        "add_select_raw": "SELECT [t].*, t.amount * ? as taxed FROM (SELECT * FROM [orders]) AS [t]",
        "combined": "WITH [recent] AS (SELECT * FROM [orders] WHERE [orders].[created_at] >= ?) SELECT [w].[user_id], max(w.weighted) + ? as top FROM (SELECT [orders].[user_id], sum(amount) * ? as weighted FROM [orders] WHERE [orders].[amount] > ? GROUP BY [orders].[user_id]) AS [w] INNER JOIN [users] ON [users].[id] = [w].[user_id] WHERE [users].[active] = ? GROUP BY [w].[user_id] HAVING count(*) > ? ORDER BY [w].[user_id] ASC OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY",
    },
}


def qb(grammar, table=""):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


class TestCteFromSubGrammar(unittest.TestCase):
    def test_with_query_renders_the_cte_before_the_select(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                totals = (
                    qb(grammar, "orders")
                    .select("user_id")
                    .select_raw("sum(amount) as total")
                    .where("status", "paid")
                    .group_by("user_id")
                )
                q = (
                    qb(grammar, "users")
                    .where("users.active", 1)
                    .join("totals", "totals.user_id", "=", "users.id")
                    .with_query("totals", totals)
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["cte"])
                self.assertEqual(list(q.get_bindings()), ["paid", 1])

    def test_several_ctes_render_in_call_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar, "b")
                    .with_query("a", qb(grammar, "orders").where("x", 1))
                    .with_query("b", lambda sub: sub.table("a").where("y", 2))
                    .where("z", 3)
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["multi"])
                self.assertEqual(list(q.get_bindings()), [1, 2, 3])

    def test_from_sub_replaces_the_table_and_aliases_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                counts = (
                    qb(grammar, "orders")
                    .select("user_id")
                    .select_raw("count(*) as n")
                    .where("status", "paid")
                    .group_by("user_id")
                )
                q = qb(grammar, "users").from_sub(counts, "t").where("t.n", ">", 2)
                self.assertEqual(q.to_qmark(), EXPECTED[name]["from_sub"])
                self.assertEqual(list(q.get_bindings()), ["paid", 2])

    def test_add_select_raw_selects_the_derived_table(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar, "users")
                    .from_sub(qb(grammar, "orders"), "t")
                    .add_select_raw("t.amount * ? as taxed", [2])
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["add_select_raw"])
                self.assertEqual(list(q.get_bindings()), [2])

    def test_bindings_follow_clause_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                weighted = (
                    qb(grammar, "orders")
                    .select("user_id")
                    .select_raw("sum(amount) * ? as weighted", [3])
                    .where("amount", ">", 10)
                    .group_by("user_id")
                )
                q = (
                    qb(grammar, "users")
                    .order_by("w.user_id")
                    .having_raw("count(*) > ?", [0])
                    .where("users.active", 1)
                    .join("users", "users.id", "=", "w.user_id")
                    .from_sub(weighted, "w")
                    .select("w.user_id")
                    .select_raw("max(w.weighted) + ? as top", [1])
                    .with_query("recent", qb(grammar, "orders").where("created_at", ">=", "2026-10-01"))
                    .group_by("w.user_id")
                    .limit(10)
                    .offset(20)
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["combined"])
                self.assertEqual(list(q.get_bindings()), ["2026-10-01", 1, 3, 10, 1, 0])

    def test_recompiling_does_not_duplicate_bindings(self):
        q = qb(SQLiteGrammar, "users").with_query("a", qb(SQLiteGrammar, "orders").where("x", 1))
        q.from_sub(qb(SQLiteGrammar, "a").where("y", 2), "t")

        self.assertEqual(q.to_qmark(), q.to_qmark())
        self.assertEqual(list(q.get_bindings()), [1, 2])

    def test_to_sql_inlines_values_for_display(self):
        q = qb(SQLiteGrammar, "users").with_query("a", qb(SQLiteGrammar, "orders").where("x", 1))
        q.from_sub(qb(SQLiteGrammar, "a").where("y", 2), "t")

        self.assertEqual(
            q.to_sql(),
            'WITH "a" AS (SELECT * FROM "orders" WHERE "orders"."x" = \'1\') '
            'SELECT * FROM (SELECT * FROM "a" WHERE "a"."y" = \'2\') AS "t"',
        )

    def test_a_non_builder_subquery_is_rejected(self):
        q = qb(SQLiteGrammar, "users")
        for method, call in (
            ("with_query", lambda: q.with_query("a", "SELECT 1")),
            ("from_sub", lambda: q.from_sub("SELECT 1", "t")),
            ("select_sub", lambda: q.select_sub("SELECT 1", "t")),
        ):
            with self.subTest(method=method):
                with self.assertRaisesRegex(TypeError, rf"{method}\(\) expects a QueryBuilder subquery"):
                    call()

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
        "select_raw": 'SELECT count(*) as total, sum(amount) as revenue FROM "orders"',
        "add_select_raw": 'SELECT "orders".*, amount * ? as taxed FROM "orders"',
        "append": 'SELECT "orders"."user_id", count(*) as total FROM "orders" GROUP BY "orders"."user_id"',
        "combined": 'SELECT "orders"."user_id", sum(case when status = ? then amount else 0 end) as paid FROM "orders" INNER JOIN "users" ON "users"."id" = "orders"."user_id" WHERE "orders"."amount" > ? GROUP BY "orders"."user_id" HAVING count(*) > ? AND sum(amount) < ? ORDER BY (SELECT "users"."name" FROM "users" WHERE users.id = orders.user_id AND "users"."active" = ? LIMIT 1) ASC',
    },
    "mysql": {
        "select_raw": "SELECT count(*) as total, sum(amount) as revenue FROM `orders`",
        "add_select_raw": "SELECT `orders`.*, amount * ? as taxed FROM `orders`",
        "append": "SELECT `orders`.`user_id`, count(*) as total FROM `orders` GROUP BY `orders`.`user_id`",
        "combined": "SELECT `orders`.`user_id`, sum(case when status = ? then amount else 0 end) as paid FROM `orders` INNER JOIN `users` ON `users`.`id` = `orders`.`user_id` WHERE `orders`.`amount` > ? GROUP BY `orders`.`user_id` HAVING count(*) > ? AND sum(amount) < ? ORDER BY (SELECT `users`.`name` FROM `users` WHERE users.id = orders.user_id AND `users`.`active` = ? LIMIT 1) ASC",
    },
    "postgres": {
        "select_raw": 'SELECT count(*) as total, sum(amount) as revenue FROM "orders"',
        "add_select_raw": 'SELECT "orders".*, amount * ? as taxed FROM "orders"',
        "append": 'SELECT "orders"."user_id", count(*) as total FROM "orders" GROUP BY "orders"."user_id"',
        "combined": 'SELECT "orders"."user_id", sum(case when status = ? then amount else 0 end) as paid FROM "orders" INNER JOIN "users" ON "users"."id" = "orders"."user_id" WHERE "orders"."amount" > ? GROUP BY "orders"."user_id" HAVING count(*) > ? AND sum(amount) < ? ORDER BY (SELECT "users"."name" FROM "users" WHERE users.id = orders.user_id AND "users"."active" = ? LIMIT 1) ASC',
    },
    "mssql": {
        "select_raw": "SELECT count(*) as total, sum(amount) as revenue FROM [orders]",
        "add_select_raw": "SELECT [orders].*, amount * ? as taxed FROM [orders]",
        "append": "SELECT [orders].[user_id], count(*) as total FROM [orders] GROUP BY [orders].[user_id]",
        "combined": "SELECT [orders].[user_id], sum(case when status = ? then amount else 0 end) as paid FROM [orders] INNER JOIN [users] ON [users].[id] = [orders].[user_id] WHERE [orders].[amount] > ? GROUP BY [orders].[user_id] HAVING count(*) > ? AND sum(amount) < ? ORDER BY (SELECT TOP 1 [users].[name] FROM [users] WHERE users.id = orders.user_id AND [users].[active] = ?) ASC",
    },
}


def qb(grammar, table):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


class TestSelectRawGrammar(unittest.TestCase):
    def test_select_raw_renders_verbatim(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar, "orders").select_raw("count(*) as total, sum(amount) as revenue")
                self.assertEqual(q.to_qmark(), EXPECTED[name]["select_raw"])
                self.assertEqual(list(q.get_bindings()), [])

    def test_add_select_raw_keeps_table_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar, "orders").add_select_raw("amount * ? as taxed", [1.2])
                self.assertEqual(q.to_qmark(), EXPECTED[name]["add_select_raw"])
                self.assertEqual(list(q.get_bindings()), [1.2])

    def test_select_raw_appends_to_selected_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                for q in (
                    qb(grammar, "orders").select("user_id").select_raw("count(*) as total"),
                    qb(grammar, "orders").select("user_id").add_select_raw("count(*) as total"),
                ):
                    self.assertEqual(q.group_by("user_id").to_sql(), EXPECTED[name]["append"])

    def test_bindings_follow_clause_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                subquery = (
                    qb(grammar, "users")
                    .select("name")
                    .where_column("users.id", "orders.user_id")
                    .where("users.active", 1)
                    .limit(1)
                )
                q = (
                    qb(grammar, "orders")
                    .order_by(subquery)
                    .select("user_id")
                    .select_raw("sum(case when status = ? then amount else 0 end) as paid", ["paid"])
                    .join("users", "users.id", "=", "orders.user_id")
                    .where("orders.amount", ">", 10)
                    .group_by("user_id")
                    .having_raw("count(*) > ?", [1])
                    .having_raw("sum(amount) < ?", (500,))
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["combined"])
                self.assertEqual(list(q.get_bindings()), ["paid", 10, 1, 500, 1])

    def test_bindings_must_be_a_list_or_tuple(self):
        q = qb(SQLiteGrammar, "orders")
        with self.assertRaisesRegex(ValueError, "Bindings must be tuple or list"):
            q.select_raw("amount * ? as taxed", "1")
        with self.assertRaisesRegex(ValueError, "Bindings must be tuple or list"):
            q.having_raw("count(*) > ?", 1)


class TestSelectRawPostgresShapes(unittest.TestCase):
    def test_grouped_page_counts(self):
        q = qb(PostgresGrammar, "st_pages").select("site_id").select_raw("COUNT(*) AS pages").group_by("site_id")

        self.assertEqual(
            q.to_qmark(),
            'SELECT "st_pages"."site_id", COUNT(*) AS pages FROM "st_pages" GROUP BY "st_pages"."site_id"',
        )
        self.assertEqual(list(q.get_bindings()), [])

    def test_grouped_opens_since_with_join(self):
        q = (
            qb(PostgresGrammar, "st_user_pages")
            .join("st_pages", "st_pages.id", "=", "st_user_pages.page_id")
            .where("st_user_pages.last_opened_at", ">=", "2026-10-01")
            .select("st_pages.site_id")
            .select_raw("COUNT(*) AS opens")
            .group_by("st_pages.site_id")
        )

        self.assertEqual(
            q.to_qmark(),
            'SELECT "st_pages"."site_id", COUNT(*) AS opens FROM "st_user_pages" '
            'INNER JOIN "st_pages" ON "st_pages"."id" = "st_user_pages"."page_id" '
            'WHERE "st_user_pages"."last_opened_at" >= ? GROUP BY "st_pages"."site_id"',
        )
        self.assertEqual(list(q.get_bindings()), ["2026-10-01"])

    def test_select_raw_bindings_precede_where_bindings(self):
        q = (
            qb(PostgresGrammar, "st_user_pages")
            .where("st_user_pages.user_id", 7)
            .select_raw("COUNT(*) FILTER (WHERE st_user_pages.last_opened_at >= ?) AS recent", ["2026-10-01"])
        )

        self.assertEqual(
            q.to_qmark(),
            'SELECT COUNT(*) FILTER (WHERE st_user_pages.last_opened_at >= ?) AS recent FROM "st_user_pages" '
            'WHERE "st_user_pages"."user_id" = ?',
        )
        self.assertEqual(list(q.get_bindings()), ["2026-10-01", 7])


class TestSelectRawTableAlias(unittest.TestCase):
    def test_add_select_raw_selects_the_aliased_table(self):
        q = qb(SQLiteGrammar, "orders").table("orders", "o").add_select_raw("o.amount * ? as taxed", [2])

        self.assertEqual(q.to_qmark(), 'SELECT "o".*, o.amount * ? as taxed FROM "orders" AS "o"')
        self.assertEqual(list(q.get_bindings()), [2])

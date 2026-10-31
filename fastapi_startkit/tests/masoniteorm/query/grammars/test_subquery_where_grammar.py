import unittest

from fastapi_startkit.masoniteorm.collection import Collection
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
        "where_in": 'SELECT * FROM "users" WHERE "users"."id" IN (SELECT "orders"."user_id" FROM "orders" WHERE "orders"."status" = ?)',
        "where_not_in": 'SELECT * FROM "users" WHERE "users"."id" NOT IN (SELECT "bans"."user_id" FROM "bans" WHERE "bans"."active" = ?)',
        "where_not_exists": 'SELECT * FROM "users" WHERE "users"."active" = ? AND NOT EXISTS (SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) OR NOT EXISTS (SELECT * FROM "bans" WHERE "bans"."active" = ?)',
        "add_select_exists": 'SELECT "users".*, EXISTS(SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) AS has_big_order FROM "users"',
        "combined": 'SELECT "users"."country", count(*) as total, EXISTS(SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) AS has_big_order FROM "users" INNER JOIN "teams" ON "teams"."id" = "users"."team_id" WHERE "users"."age" > ? AND NOT EXISTS (SELECT * FROM "bans" WHERE bans.user_id = users.id AND "bans"."active" = ?) AND "users"."id" IN (SELECT "orders"."user_id" FROM "orders" WHERE "orders"."status" = ?) GROUP BY "users"."country" HAVING count(*) > ? ORDER BY "country" ASC LIMIT 10 OFFSET 20',
    },
    "mysql": {
        "where_in": "SELECT * FROM `users` WHERE `users`.`id` IN (SELECT `orders`.`user_id` FROM `orders` WHERE `orders`.`status` = ?)",
        "where_not_in": "SELECT * FROM `users` WHERE `users`.`id` NOT IN (SELECT `bans`.`user_id` FROM `bans` WHERE `bans`.`active` = ?)",
        "where_not_exists": "SELECT * FROM `users` WHERE `users`.`active` = ? AND NOT EXISTS (SELECT * FROM `orders` WHERE orders.user_id = users.id AND `orders`.`total` > ?) OR NOT EXISTS (SELECT * FROM `bans` WHERE `bans`.`active` = ?)",
        "add_select_exists": "SELECT `users`.*, EXISTS(SELECT * FROM `orders` WHERE orders.user_id = users.id AND `orders`.`total` > ?) AS has_big_order FROM `users`",
        "combined": "SELECT `users`.`country`, count(*) as total, EXISTS(SELECT * FROM `orders` WHERE orders.user_id = users.id AND `orders`.`total` > ?) AS has_big_order FROM `users` INNER JOIN `teams` ON `teams`.`id` = `users`.`team_id` WHERE `users`.`age` > ? AND NOT EXISTS (SELECT * FROM `bans` WHERE bans.user_id = users.id AND `bans`.`active` = ?) AND `users`.`id` IN (SELECT `orders`.`user_id` FROM `orders` WHERE `orders`.`status` = ?) GROUP BY `users`.`country` HAVING count(*) > ? ORDER BY `country` ASC LIMIT 10 OFFSET 20",
    },
    "postgres": {
        "where_in": 'SELECT * FROM "users" WHERE "users"."id" IN (SELECT "orders"."user_id" FROM "orders" WHERE "orders"."status" = ?)',
        "where_not_in": 'SELECT * FROM "users" WHERE "users"."id" NOT IN (SELECT "bans"."user_id" FROM "bans" WHERE "bans"."active" = ?)',
        "where_not_exists": 'SELECT * FROM "users" WHERE "users"."active" = ? AND NOT EXISTS (SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) OR NOT EXISTS (SELECT * FROM "bans" WHERE "bans"."active" = ?)',
        "add_select_exists": 'SELECT "users".*, EXISTS(SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) AS has_big_order FROM "users"',
        "combined": 'SELECT "users"."country", count(*) as total, EXISTS(SELECT * FROM "orders" WHERE orders.user_id = users.id AND "orders"."total" > ?) AS has_big_order FROM "users" INNER JOIN "teams" ON "teams"."id" = "users"."team_id" WHERE "users"."age" > ? AND NOT EXISTS (SELECT * FROM "bans" WHERE bans.user_id = users.id AND "bans"."active" = ?) AND "users"."id" IN (SELECT "orders"."user_id" FROM "orders" WHERE "orders"."status" = ?) GROUP BY "users"."country" HAVING count(*) > ? ORDER BY "country" ASC LIMIT 10 OFFSET 20',
    },
    "mssql": {
        "where_in": "SELECT * FROM [users] WHERE [users].[id] IN (SELECT [orders].[user_id] FROM [orders] WHERE [orders].[status] = ?)",
        "where_not_in": "SELECT * FROM [users] WHERE [users].[id] NOT IN (SELECT [bans].[user_id] FROM [bans] WHERE [bans].[active] = ?)",
        "where_not_exists": "SELECT * FROM [users] WHERE [users].[active] = ? AND NOT EXISTS (SELECT * FROM [orders] WHERE orders.user_id = users.id AND [orders].[total] > ?) OR NOT EXISTS (SELECT * FROM [bans] WHERE [bans].[active] = ?)",
        "add_select_exists": "SELECT [users].*, CASE WHEN EXISTS(SELECT * FROM [orders] WHERE orders.user_id = users.id AND [orders].[total] > ?) THEN 1 ELSE 0 END AS has_big_order FROM [users]",
        "combined": "SELECT [users].[country], count(*) as total, CASE WHEN EXISTS(SELECT * FROM [orders] WHERE orders.user_id = users.id AND [orders].[total] > ?) THEN 1 ELSE 0 END AS has_big_order FROM [users] INNER JOIN [teams] ON [teams].[id] = [users].[team_id] WHERE [users].[age] > ? AND NOT EXISTS (SELECT * FROM [bans] WHERE bans.user_id = users.id AND [bans].[active] = ?) AND [users].[id] IN (SELECT [orders].[user_id] FROM [orders] WHERE [orders].[status] = ?) GROUP BY [users].[country] HAVING count(*) > ? ORDER BY [country] ASC OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY",
    },
}


def qb(grammar, table):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


def big_orders(grammar):
    return qb(grammar, "orders").where_column("orders.user_id", "users.id").where("orders.total", ">", 100)


class TestSubqueryWhereGrammar(unittest.TestCase):
    def test_where_in_accepts_a_builder_or_a_callable(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                for q in (
                    qb(grammar, "users").where_in(
                        "id", qb(grammar, "orders").select("user_id").where("status", "paid")
                    ),
                    qb(grammar, "users").where_in(
                        "id", lambda sub: sub.table("orders").select("user_id").where("status", "paid")
                    ),
                ):
                    self.assertEqual(q.to_qmark(), EXPECTED[name]["where_in"])
                    self.assertEqual(list(q.get_bindings()), ["paid"])

    def test_where_not_in_accepts_a_builder_or_a_callable(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                for q in (
                    qb(grammar, "users").where_not_in("id", qb(grammar, "bans").select("user_id").where("active", 1)),
                    qb(grammar, "users").where_not_in(
                        "id", lambda sub: sub.table("bans").select("user_id").where("active", 1)
                    ),
                ):
                    self.assertEqual(q.to_qmark(), EXPECTED[name]["where_not_in"])
                    self.assertEqual(list(q.get_bindings()), [1])

    def test_where_not_exists_and_or_where_not_exists(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar, "users")
                    .where("active", 1)
                    .where_not_exists(big_orders(grammar))
                    .or_where_not_exists(lambda sub: sub.table("bans").where("active", 2))
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["where_not_exists"])
                self.assertEqual(list(q.get_bindings()), [1, 100, 2])

    def test_add_select_exists_keeps_table_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar, "users").add_select_exists("has_big_order", big_orders(grammar))
                self.assertEqual(q.to_qmark(), EXPECTED[name]["add_select_exists"])
                self.assertEqual(list(q.get_bindings()), [100])

    def test_bindings_follow_clause_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar, "users")
                    .order_by("country")
                    .where("age", ">", 18)
                    .having_raw("count(*) > ?", [3])
                    .where_not_exists(
                        qb(grammar, "bans").where_column("bans.user_id", "users.id").where("bans.active", 1)
                    )
                    .select("country")
                    .select_raw("count(*) as total")
                    .add_select_exists("has_big_order", big_orders(grammar))
                    .join("teams", "teams.id", "=", "users.team_id")
                    .where_in("id", qb(grammar, "orders").select("user_id").where("status", "paid"))
                    .group_by("country")
                    .limit(10)
                    .offset(20)
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["combined"])
                self.assertEqual(list(q.get_bindings()), [100, 18, 1, "paid", 3])

    def test_iterables_are_still_bound_values(self):
        q = qb(SQLiteGrammar, "users").where_in("id", Collection([1, 2])).where_not_in("id", (n for n in (3,)))

        self.assertEqual(q.to_qmark(), 'SELECT * FROM "users" WHERE "users"."id" IN (?, ?) AND "users"."id" NOT IN (?)')
        self.assertEqual(list(q.get_bindings()), [1, 2, 3])

    def test_add_select_exists_on_an_aliased_table_appends_to_selection(self):
        q = (
            qb(SQLiteGrammar, "users")
            .table("users", "u")
            .add_select_exists("has_order", lambda sub: sub.table("orders").where_column("orders.user_id", "u.id"))
        )
        self.assertEqual(
            q.to_qmark(),
            'SELECT "u".*, EXISTS(SELECT * FROM "orders" WHERE orders.user_id = u.id) AS has_order FROM "users" AS "u"',
        )

        q = qb(SQLiteGrammar, "users").select("id").add_select_exists("has_order", qb(SQLiteGrammar, "orders"))
        self.assertEqual(q.to_sql(), 'SELECT "users"."id", EXISTS(SELECT * FROM "orders") AS has_order FROM "users"')

    def test_non_builder_subquery_raises(self):
        q = qb(SQLiteGrammar, "users")
        for method, call in (
            ("where_in", lambda: q.where_in("id", lambda sub: [1, 2])),
            ("where_not_in", lambda: q.where_not_in("id", lambda sub: None)),
            ("where_exists", lambda: q.where_exists("orders")),
            ("or_where_exists", lambda: q.or_where_exists(1)),
            ("where_not_exists", lambda: q.where_not_exists("orders")),
            ("or_where_not_exists", lambda: q.or_where_not_exists(None)),
            ("add_select_exists", lambda: q.add_select_exists("flag", "orders")),
        ):
            with self.subTest(method=method):
                with self.assertRaisesRegex(TypeError, rf"^{method}\(\) expects a QueryBuilder subquery"):
                    call()

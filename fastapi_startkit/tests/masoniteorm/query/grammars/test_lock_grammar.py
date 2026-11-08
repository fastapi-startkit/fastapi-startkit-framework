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
        "plain": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ?',
        "update": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ?',
        "share": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ?',
        "combined": 'SELECT "accounts"."id", "accounts"."balance" FROM "accounts" INNER JOIN "owners" ON "owners"."id" = "accounts"."owner_id" WHERE "accounts"."status" = ? ORDER BY "id" ASC LIMIT 2',
        "delete": 'DELETE FROM "accounts" WHERE "id" = ?',
    },
    "mysql": {
        "plain": "SELECT * FROM `accounts` WHERE `accounts`.`id` = ?",
        "update": "SELECT * FROM `accounts` WHERE `accounts`.`id` = ? FOR UPDATE",
        "share": "SELECT * FROM `accounts` WHERE `accounts`.`id` = ? LOCK IN SHARE MODE",
        "combined": "SELECT `accounts`.`id`, `accounts`.`balance` FROM `accounts` INNER JOIN `owners` ON `owners`.`id` = `accounts`.`owner_id` WHERE `accounts`.`status` = ? ORDER BY `id` ASC LIMIT 2 FOR UPDATE",
        "delete": "DELETE FROM `accounts` WHERE `accounts`.`id` = ?",
    },
    "postgres": {
        "plain": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ?',
        "update": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ? FOR UPDATE',
        "share": 'SELECT * FROM "accounts" WHERE "accounts"."id" = ? FOR SHARE',
        "combined": 'SELECT "accounts"."id", "accounts"."balance" FROM "accounts" INNER JOIN "owners" ON "owners"."id" = "accounts"."owner_id" WHERE "accounts"."status" = ? ORDER BY "id" ASC LIMIT 2 FOR UPDATE',
        "delete": 'DELETE FROM "accounts" WHERE "accounts"."id" = ?',
    },
    "mssql": {
        "plain": "SELECT * FROM [accounts] WHERE [accounts].[id] = ?",
        "update": "SELECT * FROM [accounts] WITH(ROWLOCK, UPDLOCK, HOLDLOCK) WHERE [accounts].[id] = ?",
        "share": "SELECT * FROM [accounts] WITH(ROWLOCK, HOLDLOCK) WHERE [accounts].[id] = ?",
        "combined": "SELECT TOP 2 [accounts].[id], [accounts].[balance] FROM [accounts] WITH(ROWLOCK, UPDLOCK, HOLDLOCK) INNER JOIN [owners] ON [owners].[id] = [accounts].[owner_id] WHERE [accounts].[status] = ? ORDER BY [id] ASC",
        "delete": "DELETE FROM [accounts] WHERE [accounts].[id] = ?",
    },
}


def qb(grammar):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = "accounts"
    return q


class TestLockGrammar(unittest.TestCase):
    def test_a_builder_without_a_lock_renders_no_lock_clause(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                self.assertEqual(qb(grammar).where("id", 7).to_qmark(), EXPECTED[name]["plain"])

    def test_lock_for_update_renders_the_dialect_update_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar).where("id", 7).lock_for_update()
                self.assertEqual(q.to_qmark(), EXPECTED[name]["update"])
                self.assertEqual(list(q.get_bindings()), [7])

    def test_shared_lock_renders_the_dialect_share_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar).where("id", 7).shared_lock()
                self.assertEqual(q.to_qmark(), EXPECTED[name]["share"])
                self.assertEqual(list(q.get_bindings()), [7])

    def test_the_lock_follows_joins_wheres_order_and_limit(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = (
                    qb(grammar)
                    .select("id", "balance")
                    .join("owners", "owners.id", "=", "accounts.owner_id")
                    .where("status", "open")
                    .order_by("id")
                    .limit(2)
                    .lock_for_update()
                )
                self.assertEqual(q.to_qmark(), EXPECTED[name]["combined"])
                self.assertEqual(list(q.get_bindings()), ["open"])

    def test_the_last_lock_called_wins(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar).where("id", 7).lock_for_update().shared_lock()
                self.assertEqual(q.to_qmark(), EXPECTED[name]["share"])

    def test_delete_ignores_the_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar).where("id", 7).lock_for_update().set_action("delete")
                self.assertEqual(q.to_qmark(), EXPECTED[name]["delete"])

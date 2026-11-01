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

SKIP_LOCKED = {
    "sqlite": "FOR UPDATE SKIP LOCKED",
    "mysql": "FOR UPDATE SKIP LOCKED",
    "postgres": "FOR UPDATE SKIP LOCKED",
    "mssql": "WITH(ROWLOCK, UPDLOCK, READPAST)",
}

EXPECTED = {
    "sqlite": {
        "update": 'SELECT * FROM "queues" WHERE "queues"."id" = ?',
        "share": 'SELECT * FROM "queues" WHERE "queues"."id" = ?',
        "string": 'SELECT * FROM "queues" WHERE "queues"."status" = ? ORDER BY "id" ASC LIMIT 1',
        "subquery": 'SELECT * FROM "queues" WHERE "queues"."id" IN (SELECT "queues"."id" FROM "queues" WHERE "queues"."status" = ? LIMIT 1)',
    },
    "mysql": {
        "update": "SELECT * FROM `queues` WHERE `queues`.`id` = ? FOR UPDATE",
        "share": "SELECT * FROM `queues` WHERE `queues`.`id` = ? LOCK IN SHARE MODE",
        "string": "SELECT * FROM `queues` WHERE `queues`.`status` = ? ORDER BY `id` ASC LIMIT 1 FOR UPDATE SKIP LOCKED",
        "subquery": "SELECT * FROM `queues` WHERE `queues`.`id` IN (SELECT `queues`.`id` FROM `queues` WHERE `queues`.`status` = ? LIMIT 1 FOR UPDATE SKIP LOCKED)",
    },
    "postgres": {
        "update": 'SELECT * FROM "queues" WHERE "queues"."id" = ? FOR UPDATE',
        "share": 'SELECT * FROM "queues" WHERE "queues"."id" = ? FOR SHARE',
        "string": 'SELECT * FROM "queues" WHERE "queues"."status" = ? ORDER BY "id" ASC LIMIT 1 FOR UPDATE SKIP LOCKED',
        "subquery": 'SELECT * FROM "queues" WHERE "queues"."id" IN (SELECT "queues"."id" FROM "queues" WHERE "queues"."status" = ? LIMIT 1 FOR UPDATE SKIP LOCKED)',
    },
    "mssql": {
        "update": "SELECT * FROM [queues] WITH(ROWLOCK, UPDLOCK, HOLDLOCK) WHERE [queues].[id] = ?",
        "share": "SELECT * FROM [queues] WITH(ROWLOCK, HOLDLOCK) WHERE [queues].[id] = ?",
        "string": "SELECT TOP 1 * FROM [queues] WITH(ROWLOCK, UPDLOCK, READPAST) WHERE [queues].[status] = ? ORDER BY [id] ASC",
        "subquery": "SELECT * FROM [queues] WHERE [queues].[id] IN (SELECT TOP 1 [queues].[id] FROM [queues] WITH(ROWLOCK, UPDLOCK, READPAST) WHERE [queues].[status] = ?)",
    },
}


def qb(grammar):
    return QueryBuilder(connection=None, grammar=grammar, processor=None).table("queues")


class TestLockValueGrammar(unittest.TestCase):
    def test_lock_true_takes_the_update_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                self.assertEqual(qb(grammar).where("id", 7).lock().to_qmark(), EXPECTED[name]["update"])
                self.assertEqual(qb(grammar).where("id", 7).lock(True).to_qmark(), EXPECTED[name]["update"])

    def test_lock_false_takes_the_shared_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                self.assertEqual(qb(grammar).where("id", 7).lock(False).to_qmark(), EXPECTED[name]["share"])

    def test_a_lock_string_renders_verbatim_except_on_sqlite(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = qb(grammar).where("status", "pending").order_by("id").limit(1).lock(SKIP_LOCKED[name])
                self.assertEqual(query.to_qmark(), EXPECTED[name]["string"])
                self.assertEqual(list(query._bindings), ["pending"])

    def test_a_locked_subquery_keeps_its_lock(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                claimable = qb(grammar).select("id").where("status", "pending").limit(1).lock(SKIP_LOCKED[name])
                query = qb(grammar).where_in("id", claimable)
                self.assertEqual(query.to_qmark(), EXPECTED[name]["subquery"])

    def test_the_last_lock_call_wins(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = qb(grammar).where("id", 7).lock("FOR UPDATE NOWAIT").lock_for_update()
                self.assertEqual(query.to_qmark(), EXPECTED[name]["update"])

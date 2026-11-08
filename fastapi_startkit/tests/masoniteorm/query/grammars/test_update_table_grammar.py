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
        "where": 'UPDATE "queues" SET "status" = ? WHERE "id" = ?',
        "where_in": 'UPDATE "queues" SET "status" = ? WHERE "id" IN (SELECT "queues"."id" FROM "queues" WHERE "queues"."user_id" = ?)',
    },
    "mysql": {
        "where": "UPDATE `queues` SET `queues`.`status` = ? WHERE `queues`.`id` = ?",
        "where_in": "UPDATE `queues` SET `queues`.`status` = ? WHERE `queues`.`id` IN (SELECT `queues`.`id` FROM `queues` WHERE `queues`.`user_id` = ?)",
    },
    "postgres": {
        "where": 'UPDATE "queues" SET "status" = ? WHERE "id" = ?',
        "where_in": 'UPDATE "queues" SET "status" = ? WHERE "id" IN (SELECT "queues"."id" FROM "queues" WHERE "queues"."user_id" = ?)',
    },
    "mssql": {
        "where": "UPDATE [queues] SET [queues].[status] = ? WHERE [queues].[id] = ?",
        "where_in": "UPDATE [queues] SET [queues].[status] = ? WHERE [queues].[id] IN (SELECT [queues].[id] FROM [queues] WHERE [queues].[user_id] = ?)",
    },
}


class RecordingConnection:
    def __init__(self, grammar):
        self.grammar = grammar
        self.calls = []

    def query(self):
        return QueryBuilder(connection=self, grammar=self.grammar, processor=None).table("queues")

    async def update(self, sql, bindings):
        self.calls.append((sql, bindings))
        return 1


class TestUpdateTableGrammar(unittest.IsolatedAsyncioTestCase):
    async def test_update_prefixes_columns_with_the_updated_table(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().where("id", 7).update({"status": "processing"})
                self.assertEqual(connection.calls, [(EXPECTED[name]["where"], ["processing", 7])])

    async def test_update_through_a_subquery_keeps_the_updated_table(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                subquery = connection.query().select("id").where("user_id", 3)
                await connection.query().where_in("id", subquery).update({"status": "processing"})
                self.assertEqual(connection.calls, [(EXPECTED[name]["where_in"], ["processing", 3])])

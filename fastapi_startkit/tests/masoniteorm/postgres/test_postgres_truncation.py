from fastapi_startkit.masoniteorm.testing import DatabaseTruncation

from .fixtures.db import schema
from .test_case import TestCase


class Truncation(DatabaseTruncation):
    tables_to_truncate = ["tr_owners", "tr_accounts"]


class TestPostgresTruncation(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.drop_tables()
        async with await schema.create("tr_owners") as table:
            table.increments("id")
            table.string("name")
        async with await schema.create("tr_accounts") as table:
            table.increments("id")
            table.integer("owner_id")
            table.foreign("owner_id").references("id").on("tr_owners")
        connection = schema.get_connection()
        await connection.statement("INSERT INTO tr_owners (name) VALUES ('Ada')")
        await connection.statement("INSERT INTO tr_accounts (owner_id) VALUES (1)")

    async def asyncTearDown(self):
        await self.drop_tables()
        await super().asyncTearDown()

    @staticmethod
    async def drop_tables():
        await schema.drop_table_if_exists("tr_accounts")
        await schema.drop_table_if_exists("tr_owners")

    async def test_database_truncation_empties_related_tables_and_restarts_ids(self):
        await Truncation().truncate_tables()

        connection = schema.get_connection()
        await connection.statement("INSERT INTO tr_owners (name) VALUES ('Grace')")
        self.assertEqual(await connection.select("SELECT id, name FROM tr_owners"), [{"id": 1, "name": "Grace"}])
        self.assertEqual(await connection.select("SELECT id FROM tr_accounts"), [])

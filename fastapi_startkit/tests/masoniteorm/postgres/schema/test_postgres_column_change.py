from ..fixtures.db import schema
from ..test_case import TestCase


class TestPostgresColumnChange(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await schema.drop_table_if_exists("change_targets")
        async with await schema.create("change_targets") as blueprint:
            blueprint.increments("id")
            blueprint.string("name", 50).default("anonymous")
            blueprint.string("age")
            blueprint.enum("status", ["on", "off"]).default("on")
        await schema.get_connection().statement(
            "INSERT INTO change_targets (name, age, status) VALUES ('alice', '30', 'on')"
        )

    async def asyncTearDown(self):
        await schema.drop_table_if_exists("change_targets")
        await super().asyncTearDown()

    async def column(self, name):
        rows = await schema.get_connection().select(
            "SELECT data_type, character_maximum_length, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = 'change_targets' AND column_name = ?",
            [name],
        )
        return rows[0]

    async def test_change_length_nullable_and_drops_omitted_default(self):
        async with await schema.table("change_targets") as blueprint:
            blueprint.string("name", 100).nullable().change()

        column = await self.column("name")
        self.assertEqual(column["character_maximum_length"], 100)
        self.assertEqual(column["is_nullable"], "YES")
        self.assertIsNone(column["column_default"])

    async def test_change_type_casts_existing_rows_and_sets_default(self):
        async with await schema.table("change_targets") as blueprint:
            blueprint.integer("age").default(0).change()

        connection = schema.get_connection()
        await connection.statement("INSERT INTO change_targets (name) VALUES ('bob')")
        rows = await connection.select("SELECT age FROM change_targets ORDER BY id")

        self.assertEqual([row["age"] for row in rows], [30, 0])
        self.assertEqual((await self.column("age"))["data_type"], "integer")

    async def test_change_enum_replaces_check_constraint(self):
        async with await schema.table("change_targets") as blueprint:
            blueprint.enum("status", ["on", "off", "paused"]).default("paused").change()

        connection = schema.get_connection()
        await connection.statement("INSERT INTO change_targets (name, age) VALUES ('bob', '1')")
        rows = await connection.select("SELECT status FROM change_targets ORDER BY id")

        self.assertEqual([row["status"] for row in rows], ["on", "paused"])
        with self.assertRaises(Exception):
            await connection.statement("INSERT INTO change_targets (name, age, status) VALUES ('x', '1', 'nope')")

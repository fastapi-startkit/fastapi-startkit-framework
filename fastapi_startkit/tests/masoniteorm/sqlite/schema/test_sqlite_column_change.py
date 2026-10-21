from ..test_case import TestCase


class TestSQLiteColumnChange(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("change_targets") as blueprint:
            blueprint.increments("id")
            blueprint.string("name", 50)
            blueprint.string("age")
        await self.schema.get_connection().statement("INSERT INTO change_targets (name, age) VALUES ('alice', '30')")

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("change_targets")
        await super().asyncTearDown()

    async def test_change_rebuilds_table_and_keeps_rows(self):
        async with await self.schema.table("change_targets") as blueprint:
            blueprint.string("name", 100).nullable().change()
            blueprint.integer("age").default(0).change()

        connection = self.schema.get_connection()
        await connection.statement("INSERT INTO change_targets (name) VALUES (NULL)")
        rows = await connection.select("SELECT name, age FROM change_targets ORDER BY id")

        self.assertEqual([(row["name"], row["age"]) for row in rows], [("alice", 30), (None, 0)])

    async def test_change_keeps_untouched_columns(self):
        async with await self.schema.table("change_targets") as blueprint:
            blueprint.string("name", 100).nullable().change()

        self.assertTrue(await self.schema.has_column("change_targets", "age"))
        self.assertTrue(await self.schema.has_column("change_targets", "id"))

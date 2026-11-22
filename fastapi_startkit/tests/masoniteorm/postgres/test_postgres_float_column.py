from .fixtures.db import schema
from .test_case import TestCase


class TestPostgresFloatColumn(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await schema.drop_table_if_exists("float_readings")

    async def asyncTearDown(self):
        await schema.drop_table_if_exists("float_readings")
        await super().asyncTearDown()

    async def test_float_column_is_created_and_stores_values(self):
        async with await schema.create("float_readings") as blueprint:
            blueprint.increments("id")
            blueprint.float("value")
        async with await schema.table("float_readings") as blueprint:
            blueprint.float("ratio", 8, 2, nullable=True)

        connection = schema.get_connection()
        await connection.statement("INSERT INTO float_readings (value, ratio) VALUES (?, ?)", [1.25, 0.5])
        rows = await connection.select(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'float_readings' AND column_name IN ('value', 'ratio') ORDER BY column_name"
        )

        self.assertEqual(
            [(row["column_name"], row["data_type"]) for row in rows],
            [("ratio", "double precision"), ("value", "double precision")],
        )
        self.assertEqual(
            (await connection.select("SELECT value, ratio FROM float_readings"))[0], {"value": 1.25, "ratio": 0.5}
        )

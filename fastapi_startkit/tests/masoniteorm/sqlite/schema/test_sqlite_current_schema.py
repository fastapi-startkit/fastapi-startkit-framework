from ..test_case import TestCase


class TestSQLiteCurrentSchema(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.schema.drop_table_if_exists("counters")
        async with await self.schema.create("counters") as table:
            table.increments("id")
            table.integer("views").default(0)
            table.integer("likes").nullable()
            table.string("label", 50)

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("counters")
        await self.schema.drop_table_if_exists("tallies")
        await super().asyncTearDown()

    async def current_columns(self, table_name):
        current = await self.schema.platform().get_current_schema(self.schema.get_connection(), table_name)
        return current.get_added_columns()

    async def test_plain_integer_columns_are_reported_as_integer(self):
        columns = await self.current_columns("counters")

        self.assertEqual(columns["id"].column_type, "increments")
        self.assertEqual(columns["views"].column_type, "integer")
        self.assertEqual(columns["likes"].column_type, "integer")
        self.assertEqual(columns["label"].column_type, "string")
        self.assertIs(columns["views"].column_python_type, int)

    async def test_integer_primary_key_without_autoincrement_stays_integer(self):
        async with await self.schema.create("tallies") as table:
            table.integer("id").primary()
            table.integer("total")

        columns = await self.current_columns("tallies")

        self.assertEqual(columns["id"].column_type, "integer")
        self.assertEqual(columns["total"].column_type, "integer")

    async def test_alter_rebuild_keeps_plain_integer_columns(self):
        blueprint = await self.schema.table("counters")
        blueprint.rename("likes", "hearts", "integer")

        sql = "\n".join(await blueprint.to_sql())

        self.assertEqual(sql.count("AUTOINCREMENT"), 1)
        self.assertIn('"id" INTEGER PRIMARY KEY AUTOINCREMENT', sql)
        self.assertIn('"views" INTEGER NOT NULL DEFAULT 0', sql)

    async def test_defaults_are_parsed_back_from_sql_literals(self):
        async with await self.schema.create("tallies") as table:
            table.integer("total").default(5)
            table.boolean("active").default(True)
            table.string("note").default("draft")
            table.string("empty").default("")
            table.timestamp("seen_at").default("current")
            table.string("maybe").nullable()

        columns = await self.current_columns("tallies")

        self.assertEqual(columns["total"].default, 5)
        self.assertEqual(columns["note"].default, "draft")
        self.assertEqual(columns["active"].default, "True")
        self.assertTrue(columns["active"].default_is_raw)
        self.assertEqual(columns["empty"].default, "")
        self.assertEqual(columns["seen_at"].default, "current")
        self.assertIsNone(columns["maybe"].default)

    async def test_unknown_default_expressions_are_kept_raw(self):
        platform = self.schema.platform()

        self.assertEqual(platform._parse_default("1.5"), (1.5, False))
        self.assertEqual(platform._parse_default("'it''s'"), ("it's", False))
        self.assertEqual(platform._parse_default("NULL"), (None, False))
        self.assertEqual(platform._parse_default("(datetime('now'))"), ("(datetime('now'))", True))

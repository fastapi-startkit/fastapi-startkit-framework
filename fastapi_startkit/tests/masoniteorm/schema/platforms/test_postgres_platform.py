import unittest

from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff
from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform


class TestPostgresPlatformCreate(unittest.TestCase):
    """Schema SQL generation for Postgres — pure string compilation, no live connection."""

    def setUp(self):
        self.platform = PostgresPlatform()

    def _basic_table(self):
        table = Table("users")
        table.add_column("id", "integer", primary=True)
        table.add_column("name", "string", length=255)
        table.add_column("bio", "string", length=255, nullable=True)
        return table

    def test_compile_create_sql(self):
        sql = self.platform.compile_create_sql(self._basic_table())
        self.assertEqual(
            sql,
            ['CREATE TABLE "users" ("id" INTEGER NOT NULL PRIMARY KEY, "name" VARCHAR(255) NOT NULL, "bio" VARCHAR(255) NULL)'],
        )

    def test_compile_create_sql_if_not_exists(self):
        sql = self.platform.compile_create_sql(self._basic_table(), if_not_exists=True)
        self.assertTrue(sql[0].startswith('CREATE TABLE IF NOT EXISTS "users"'))

    def test_create_with_enum_check_constraint(self):
        table = Table("users")
        table.add_column("status", "enum", values=["on", "off"])
        sql = self.platform.compile_create_sql(table)[0]
        self.assertIn("\"status\" VARCHAR CHECK(status IN ('on', 'off')) NOT NULL", sql)

    def test_create_with_column_comment(self):
        table = self._basic_table()
        table.get_added_columns()["name"].add_comment("full name")
        sql = self.platform.compile_create_sql(table)
        self.assertIn("""COMMENT ON COLUMN "users"."name" is 'full name'""", sql)

    def test_create_appends_index_statement(self):
        table = self._basic_table()
        table.add_index(["email"], "users_email_index", "index")
        sql = self.platform.compile_create_sql(table)
        self.assertEqual(sql[1], 'CREATE INDEX users_email_index ON "users"(email)')

    def test_integer_types_have_no_length(self):
        table = Table("users")
        table.add_column("count", "integer", length=11)
        sql = self.platform.compile_create_sql(table)[0]
        self.assertIn('"count" INTEGER NOT NULL', sql)


class TestPostgresPlatformAlter(unittest.TestCase):
    def setUp(self):
        self.platform = PostgresPlatform()

    def test_add_column(self):
        diff = TableDiff("users")
        diff.add_column("age", "integer")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['ALTER TABLE "users" ADD COLUMN "age" INTEGER NOT NULL'],
        )

    def test_drop_column(self):
        diff = TableDiff("users")
        diff.drop_column("age")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['ALTER TABLE "users" DROP COLUMN "age"'],
        )

    def test_add_foreign_key(self):
        diff = TableDiff("users")
        diff.add_foreign_key("profile_id", table="profiles", foreign_column="id").on_delete("cascade")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                'ALTER TABLE "users" ADD CONSTRAINT users_profile_id_foreign FOREIGN KEY ("profile_id") '
                'REFERENCES "profiles"("id") ON DELETE CASCADE'
            ],
        )

    def test_rename_column(self):
        diff = TableDiff("users")
        diff.rename_column("old", "new", "string", length=255)
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['ALTER TABLE "users" RENAME COLUMN "old" TO "new"'],
        )

    def test_change_column(self):
        from fastapi_startkit.masoniteorm.schema.Column import Column

        column = Column("age", "integer")
        column.default = 5
        diff = TableDiff("users")
        diff.changed_columns = {"age": column}
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                'ALTER TABLE "users" ALTER COLUMN "age" TYPE INTEGER, '
                'ALTER COLUMN "age" SET NOT NULL, ALTER COLUMN "age" SET DEFAULT 5'
            ],
        )

    def test_add_primary_key_constraint(self):
        diff = TableDiff("users")
        diff.add_constraint("pk", "primary_key", columns=["id"])
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['ALTER TABLE "users" ADD CONSTRAINT pk PRIMARY KEY (id)'],
        )

    def test_add_index(self):
        diff = TableDiff("users")
        diff.add_index(["email"], "users_email_index", "index")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['CREATE INDEX users_email_index ON "users"(email)'],
        )

    def test_add_unique_constraint(self):
        diff = TableDiff("users")
        diff.add_constraint("u_uniq", "unique", columns=["email"])
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ['ALTER TABLE "users" ADD CONSTRAINT u_uniq UNIQUE(email)'],
        )

    def test_drop_foreign_key_and_index(self):
        diff = TableDiff("users")
        diff.drop_foreign("fk_1")
        diff.remove_index("idx_1")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["DROP INDEX idx_1", 'ALTER TABLE "users" DROP CONSTRAINT fk_1'],
        )

    def test_table_comment(self):
        diff = TableDiff("users")
        diff.add_column("x", "integer")
        diff.add_comment("a table")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                'ALTER TABLE "users" ADD COLUMN "x" INTEGER NOT NULL',
                'COMMENT ON TABLE "users" is \'a table\'',
            ],
        )


class TestPostgresPlatformHelpers(unittest.TestCase):
    def setUp(self):
        self.platform = PostgresPlatform()

    def test_compile_drop_table(self):
        self.assertEqual(self.platform.compile_drop_table("users"), 'DROP TABLE "users" CASCADE')

    def test_compile_drop_table_if_exists(self):
        self.assertEqual(
            self.platform.compile_drop_table_if_exists("users"),
            'DROP TABLE IF EXISTS "users" CASCADE',
        )

    def test_compile_rename_table(self):
        self.assertEqual(
            self.platform.compile_rename_table("users", "clients"),
            'ALTER TABLE "users" RENAME TO "clients"',
        )

    def test_compile_truncate(self):
        self.assertEqual(self.platform.compile_truncate("users"), 'TRUNCATE "users"')

    def test_compile_truncate_with_foreign_keys(self):
        self.assertEqual(
            self.platform.compile_truncate("users", foreign_keys=True),
            [
                'ALTER TABLE "users" DISABLE TRIGGER ALL',
                'TRUNCATE "users"',
                'ALTER TABLE "users" ENABLE TRIGGER ALL',
            ],
        )

    def test_compile_table_exists_defaults_to_public(self):
        self.assertEqual(
            self.platform.compile_table_exists("users"),
            "SELECT * from information_schema.tables where table_name='users' AND table_schema = 'public'",
        )

    def test_compile_table_exists_with_schema(self):
        self.assertEqual(
            self.platform.compile_table_exists("users", schema="app"),
            "SELECT * from information_schema.tables where table_name='users' AND table_schema = 'app'",
        )

    def test_compile_column_exists(self):
        self.assertEqual(
            self.platform.compile_column_exists("users", "name"),
            "SELECT column_name FROM information_schema.columns WHERE table_name='users' and column_name='name'",
        )

    def test_compile_get_all_tables(self):
        self.assertEqual(
            self.platform.compile_get_all_tables(database="app"),
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
            "AND table_catalog = 'app' AND table_type = 'BASE TABLE'",
        )

    def test_foreign_key_toggles_are_noops(self):
        self.assertEqual(self.platform.enable_foreign_key_constraints(), "")
        self.assertEqual(self.platform.disable_foreign_key_constraints(), "")

    def test_wrap_helpers(self):
        self.assertEqual(self.platform.wrap_table("users"), '"users"')
        self.assertEqual(self.platform.wrap_column("name"), '"name"')


if __name__ == "__main__":
    unittest.main()

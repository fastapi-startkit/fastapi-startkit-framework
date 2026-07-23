import unittest

from fastapi_startkit.masoniteorm.schema.Column import Column
from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff
from fastapi_startkit.masoniteorm.schema.platforms import MSSQLPlatform


class TestMSSQLPlatformCreate(unittest.TestCase):
    """Schema SQL generation for MSSQL — pure string compilation, no live connection."""

    def setUp(self):
        self.platform = MSSQLPlatform()

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
            [
                "CREATE TABLE [users] ([id] INT NOT NULL PRIMARY KEY, [name] VARCHAR(255) NOT NULL, [bio] VARCHAR(255) NULL)"
            ],
        )

    def test_compile_create_sql_if_not_exists(self):
        sql = self.platform.compile_create_sql(self._basic_table(), if_not_exists=True)
        self.assertTrue(sql[0].startswith("CREATE TABLE IF NOT EXISTS [users]"))

    def test_create_with_enum_check_constraint(self):
        table = Table("users")
        table.add_column("status", "enum", values=["on", "off"])
        sql = self.platform.compile_create_sql(table)[0]
        self.assertIn("[status] VARCHAR NOT NULL CHECK([status] IN ('on', 'off'))", sql)

    def test_create_with_foreign_key(self):
        table = self._basic_table()
        table.add_foreign_key("profile_id", table="profiles", foreign_column="id").on_delete("cascade")
        sql = self.platform.compile_create_sql(table)[0]
        self.assertIn(
            "CONSTRAINT users_profile_id_foreign FOREIGN KEY ([profile_id]) REFERENCES [profiles]([id]) ON DELETE CASCADE",
            sql,
        )

    def test_create_appends_index_statement(self):
        table = self._basic_table()
        table.add_index(["email"], "users_email_index", "index")
        sql = self.platform.compile_create_sql(table)
        self.assertEqual(sql[1], "CREATE INDEX users_email_index ON [users](email)")


class TestMSSQLPlatformAlter(unittest.TestCase):
    def setUp(self):
        self.platform = MSSQLPlatform()

    def test_add_column(self):
        diff = TableDiff("users")
        diff.add_column("age", "integer")
        self.assertEqual(self.platform.compile_alter_sql(diff), ["ALTER TABLE [users] ADD [age] INT NOT NULL"])

    def test_change_column(self):
        diff = TableDiff("users")
        diff.changed_columns = {"age": Column("age", "integer")}
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE [users] ALTER COLUMN [age] INT NOT NULL"],
        )

    def test_rename_column(self):
        diff = TableDiff("users")
        diff.rename_column("old_name", "new_name", "string", length=255)
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["EXEC sp_rename 'users.old_name', 'new_name', 'COLUMN'"],
        )

    def test_drop_column(self):
        diff = TableDiff("users")
        diff.drop_column("age")
        self.assertEqual(self.platform.compile_alter_sql(diff), ["ALTER TABLE [users] DROP COLUMN age"])

    def test_add_foreign_key(self):
        diff = TableDiff("users")
        diff.add_foreign_key("profile_id", table="profiles", foreign_column="id").on_delete("cascade")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                "ALTER TABLE [users] ADD CONSTRAINT users_profile_id_foreign FOREIGN KEY ([profile_id]) "
                "REFERENCES [profiles]([id]) ON DELETE CASCADE"
            ],
        )

    def test_add_primary_key_constraint(self):
        diff = TableDiff("users")
        diff.add_constraint("pk", "primary_key", columns=["id"])
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE [users] ADD CONSTRAINT pk PRIMARY KEY (id)"],
        )

    def test_drop_foreign_key(self):
        diff = TableDiff("users")
        diff.drop_foreign("fk_1")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE [users] DROP CONSTRAINT fk_1"],
        )

    def test_remove_index(self):
        diff = TableDiff("users")
        diff.remove_index("idx_1")
        self.assertEqual(self.platform.compile_alter_sql(diff), ["DROP INDEX [users].[idx_1]"])


class TestMSSQLPlatformHelpers(unittest.TestCase):
    def setUp(self):
        self.platform = MSSQLPlatform()

    def test_compile_drop_table(self):
        self.assertEqual(self.platform.compile_drop_table("users"), "DROP TABLE [users]")

    def test_compile_drop_table_if_exists(self):
        self.assertEqual(self.platform.compile_drop_table_if_exists("users"), "DROP TABLE IF EXISTS [users]")

    def test_compile_rename_table(self):
        self.assertEqual(
            self.platform.compile_rename_table("users", "clients"),
            "EXEC sp_rename [users], [clients]",
        )

    def test_compile_truncate(self):
        self.assertEqual(self.platform.compile_truncate("users"), "TRUNCATE TABLE [users]")

    def test_compile_truncate_with_foreign_keys(self):
        self.assertEqual(
            self.platform.compile_truncate("users", foreign_keys=True),
            [
                "ALTER TABLE [users] NOCHECK CONSTRAINT ALL",
                "TRUNCATE TABLE [users]",
                "ALTER TABLE [users] WITH CHECK CHECK CONSTRAINT ALL",
            ],
        )

    def test_compile_table_exists(self):
        self.assertEqual(
            self.platform.compile_table_exists("users"),
            "SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'users'",
        )

    def test_compile_column_exists(self):
        self.assertEqual(
            self.platform.compile_column_exists("users", "name"),
            "SELECT 1 FROM sys.columns WHERE Name = N'name' AND Object_ID = Object_ID(N'users')",
        )

    def test_compile_get_all_tables(self):
        self.assertEqual(self.platform.compile_get_all_tables("app"), "SELECT name FROM app.sys.tables")

    def test_foreign_key_toggles_are_noops(self):
        self.assertEqual(self.platform.enable_foreign_key_constraints(), "")
        self.assertEqual(self.platform.disable_foreign_key_constraints(), "")

    def test_rename_column_string(self):
        self.assertEqual(
            self.platform.rename_column_string("users", "old", "new"),
            "EXEC sp_rename 'users.old', 'new', 'COLUMN'",
        )

    def test_get_current_schema_returns_table(self):
        table = self.platform.get_current_schema(connection=None, table_name="users")
        self.assertEqual(table.name, "users")

    def test_wrap_helpers(self):
        self.assertEqual(self.platform.wrap_table("users"), "[users]")
        self.assertEqual(self.platform.wrap_column("name"), "[name]")

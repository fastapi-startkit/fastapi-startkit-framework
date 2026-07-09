import unittest

from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff
from fastapi_startkit.masoniteorm.schema.platforms import MySQLPlatform


class TestMySQLPlatformCreate(unittest.TestCase):
    """Schema SQL generation for MySQL — pure string compilation, no live connection."""

    def setUp(self):
        self.platform = MySQLPlatform()

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
            ["CREATE TABLE `users` (`id` INT NOT NULL PRIMARY KEY, `name` VARCHAR(255) NOT NULL, `bio` VARCHAR(255) NULL)"],
        )

    def test_compile_create_sql_if_not_exists(self):
        sql = self.platform.compile_create_sql(self._basic_table(), if_not_exists=True)
        self.assertTrue(sql[0].startswith("CREATE TABLE IF NOT EXISTS `users`"))

    def test_create_with_defaults_enum_and_foreign_key(self):
        table = Table("users")
        table.add_column("active", "integer", default=0)
        table.add_column("role", "string", default="admin")
        table.add_column("status", "enum", values=["on", "off"])
        table.add_column("created", "timestamp", default="current")
        table.add_foreign_key("profile_id", table="profiles", foreign_column="id").on_delete("cascade")

        sql = self.platform.compile_create_sql(table)[0]

        self.assertIn("`active` INT NOT NULL DEFAULT 0", sql)
        self.assertIn("`role` VARCHAR NOT NULL DEFAULT 'admin'", sql)
        self.assertIn("`status` ENUM('on', 'off') NOT NULL", sql)
        self.assertIn("`created` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", sql)
        self.assertIn(
            "CONSTRAINT users_profile_id_foreign FOREIGN KEY (`profile_id`) REFERENCES `profiles`(`id`) ON DELETE CASCADE",
            sql,
        )

    def test_create_appends_index_statement(self):
        table = self._basic_table()
        table.add_index(["email"], "users_email_index", "index")

        sql = self.platform.compile_create_sql(table)

        self.assertEqual(sql[1], "CREATE INDEX users_email_index ON `users`(email)")

    def test_columnize_unsigned_and_comment(self):
        table = Table("stats")
        column = table.add_column("views", "integer")
        column.unsigned()
        column.add_comment("hits")

        self.assertEqual(
            self.platform.columnize(table.get_added_columns()),
            ["`views` INT UNSIGNED NOT NULL COMMENT 'hits'"],
        )


class TestMySQLPlatformAlter(unittest.TestCase):
    def setUp(self):
        self.platform = MySQLPlatform()

    def test_add_column(self):
        diff = TableDiff("users")
        diff.add_column("age", "integer")
        self.assertEqual(self.platform.compile_alter_sql(diff), ["ALTER TABLE `users` ADD `age` INT NOT NULL"])

    def test_add_column_with_default_and_enum(self):
        diff = TableDiff("users")
        diff.add_column("role", "string", default="admin")
        diff.add_column("st", "enum", values=["a", "b"])
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE `users` ADD `role` VARCHAR NOT NULL DEFAULT 'admin', ADD `st` ENUM('a', 'b') NOT NULL"],
        )

    def test_rename_column(self):
        diff = TableDiff("users")
        diff.rename_column("old", "new", "string", length=255)
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE `users` CHANGE `old` `new` VARCHAR(255) NOT NULL"],
        )

    def test_change_column(self):
        from fastapi_startkit.masoniteorm.schema.Column import Column

        diff = TableDiff("users")
        diff.changed_columns = {"age": Column("age", "integer")}
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE `users` MODIFY `age` INT NOT NULL"],
        )

    def test_drop_column(self):
        diff = TableDiff("users")
        diff.drop_column("age")
        self.assertEqual(self.platform.compile_alter_sql(diff), ["ALTER TABLE `users` DROP COLUMN `age`"])

    def test_add_foreign_key(self):
        diff = TableDiff("users")
        diff.add_foreign_key("profile_id", table="profiles", foreign_column="id").on_delete("cascade")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                "ALTER TABLE `users` ADD CONSTRAINT users_profile_id_foreign FOREIGN KEY (profile_id) "
                "REFERENCES profiles(id) ON DELETE CASCADE"
            ],
        )

    def test_add_index(self):
        diff = TableDiff("users")
        diff.add_index(["email"], "users_email_index", "index")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["CREATE INDEX users_email_index ON `users`(email)"],
        )

    def test_add_unique_constraint(self):
        diff = TableDiff("users")
        diff.add_constraint("u_uniq", "unique", columns=["email"])
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            ["ALTER TABLE `users` ADD CONSTRAINT UNIQUE INDEX u_uniq(email)"],
        )

    def test_drop_foreign_key_and_index(self):
        diff = TableDiff("users")
        diff.drop_foreign("fk_1")
        diff.remove_index("idx_1")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                "ALTER TABLE `users` DROP FOREIGN KEY fk_1",
                "ALTER TABLE `users` DROP INDEX idx_1",
            ],
        )

    def test_table_comment(self):
        diff = TableDiff("users")
        diff.add_column("x", "integer")
        diff.add_comment("a table")
        self.assertEqual(
            self.platform.compile_alter_sql(diff),
            [
                "ALTER TABLE `users` ADD `x` INT NOT NULL",
                "ALTER TABLE `users` COMMENT 'a table'",
            ],
        )


class TestMySQLPlatformHelpers(unittest.TestCase):
    def setUp(self):
        self.platform = MySQLPlatform()

    def test_compile_drop_table(self):
        self.assertEqual(self.platform.compile_drop_table("users"), "DROP TABLE `users`")

    def test_compile_drop_table_if_exists(self):
        self.assertEqual(self.platform.compile_drop_table_if_exists("users"), "DROP TABLE IF EXISTS `users`")

    def test_compile_rename_table(self):
        self.assertEqual(
            self.platform.compile_rename_table("users", "clients"),
            "ALTER TABLE `users` RENAME TO `clients`",
        )

    def test_compile_truncate(self):
        self.assertEqual(self.platform.compile_truncate("users"), "TRUNCATE `users`")

    def test_compile_truncate_with_foreign_keys(self):
        self.assertEqual(
            self.platform.compile_truncate("users", foreign_keys=True),
            ["SET FOREIGN_KEY_CHECKS=0", "TRUNCATE `users`", "SET FOREIGN_KEY_CHECKS=1"],
        )

    def test_compile_table_exists(self):
        self.assertEqual(
            self.platform.compile_table_exists("users", database="app"),
            "SELECT * from information_schema.tables where table_name='users' AND table_schema = 'app'",
        )

    def test_compile_column_exists(self):
        self.assertEqual(
            self.platform.compile_column_exists("users", "name"),
            "SELECT column_name FROM information_schema.columns WHERE table_name='users' and column_name='name'",
        )

    def test_compile_get_all_tables(self):
        self.assertEqual(
            self.platform.compile_get_all_tables("app"),
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'app'",
        )

    def test_foreign_key_toggles(self):
        self.assertEqual(self.platform.enable_foreign_key_constraints(), "SET FOREIGN_KEY_CHECKS=1")
        self.assertEqual(self.platform.disable_foreign_key_constraints(), "SET FOREIGN_KEY_CHECKS=0")

    def test_wrap_helpers(self):
        self.assertEqual(self.platform.wrap_table("users"), "`users`")
        self.assertEqual(self.platform.wrap_column("name"), "`name`")

    def test_get_column_length(self):
        self.assertEqual(self.platform.get_column_length("VARCHAR(255)"), "255")
        self.assertIsNone(self.platform.get_column_length("INT"))

    def test_get_column_type(self):
        reversed_map = {v: k for k, v in self.platform.type_map.items()}
        self.assertEqual(self.platform.get_column_type(reversed_map, "CHAR(1)"), "char")
        self.assertEqual(self.platform.get_column_type(reversed_map, "INT"), "integer")


if __name__ == "__main__":
    unittest.main()

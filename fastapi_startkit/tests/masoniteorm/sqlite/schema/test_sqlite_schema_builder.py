from unittest.mock import AsyncMock, MagicMock


from ..test_case import TestCase


class TestSQLiteSchemaBuilder(TestCase):
    async def test_can_add_columns(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name")
            blueprint.integer("age")

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE TABLE "users" ("name" VARCHAR(255) NOT NULL, "age" INTEGER NOT NULL)'],
        )

    async def test_can_add_tiny_text(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.tiny_text("description")

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE TABLE "users" ("description" TEXT NOT NULL)'],
        )

    async def test_can_add_unsigned_decimal(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.unsigned_decimal("amount", 19, 4)

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE TABLE "users" ("amount" DECIMAL(19, 4) NOT NULL)'],
        )

    async def test_can_create_table_if_not_exists(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create_table_if_not_exists("users") as blueprint:
            blueprint.string("name")
            blueprint.integer("age")

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE TABLE IF NOT EXISTS "users" ("name" VARCHAR(255) NOT NULL, "age" INTEGER NOT NULL)'],
        )

    async def test_can_add_columns_with_constraint(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name")
            blueprint.integer("age")
            blueprint.unique("name")

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE TABLE "users" ("name" VARCHAR(255) NOT NULL, "age" INTEGER NOT NULL, UNIQUE(name))'],
        )

    async def test_can_have_float_type(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.float("amount")

        self.assertEqual(
            await blueprint.to_sql(),
            [
                """CREATE TABLE "users" ("""
                """\"amount" FLOAT(19, 4) NOT NULL)"""
            ],
        )

    async def test_can_add_columns_with_foreign_key_constraint(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name").unique()
            blueprint.integer("age")
            blueprint.integer("profile_id")
            blueprint.foreign("profile_id").references("id").on("profiles")

        self.assertEqual(len(blueprint.table.added_columns), 3)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "users" '
                '("name" VARCHAR(255) NOT NULL, '
                '"age" INTEGER NOT NULL, '
                '"profile_id" INTEGER NOT NULL, '
                "UNIQUE(name), "
                'CONSTRAINT users_profile_id_foreign FOREIGN KEY ("profile_id") REFERENCES "profiles"("id"))'
            ],
        )

    async def test_can_add_columns_with_foreign_key_constraint_name(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name").unique()
            blueprint.integer("age")
            blueprint.integer("profile_id")
            blueprint.foreign("profile_id", name="profile_foreign").references("id").on("profiles")

        self.assertEqual(len(blueprint.table.added_columns), 3)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "users" '
                '("name" VARCHAR(255) NOT NULL, '
                '"age" INTEGER NOT NULL, '
                '"profile_id" INTEGER NOT NULL, '
                "UNIQUE(name), "
                'CONSTRAINT profile_foreign FOREIGN KEY ("profile_id") REFERENCES "profiles"("id"))'
            ],
        )

    async def test_can_use_morphs_for_polymorphism_relationships(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("likes") as blueprint:
            blueprint.morphs("record")

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "likes" ("record_id" INTEGER UNSIGNED NOT NULL, "record_type" VARCHAR NOT NULL)',
                'CREATE INDEX likes_record_id_index ON "likes"(record_id)',
                'CREATE INDEX likes_record_type_index ON "likes"(record_type)',
            ],
        )

    async def test_can_advanced_table_creation(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.increments("id")
            blueprint.string("name")
            blueprint.enum("gender", ["male", "female"])
            blueprint.string("email").unique()
            blueprint.string("password")
            blueprint.string("option").default("ADMIN")
            blueprint.integer("admin").default(0)
            blueprint.string("remember_token").nullable()
            blueprint.timestamp("verified_at").nullable()
            blueprint.unique(["email", "name"])
            blueprint.timestamps()

        self.assertEqual(len(blueprint.table.added_columns), 11)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                """CREATE TABLE "users" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "name" VARCHAR(255) NOT NULL, "gender" VARCHAR(255) CHECK(gender IN ('male', 'female')) NOT NULL, "email" VARCHAR(255) NOT NULL, """
                """"password" VARCHAR(255) NOT NULL, "option" VARCHAR(255) NOT NULL DEFAULT 'ADMIN', "admin" INTEGER NOT NULL DEFAULT 0, "remember_token" VARCHAR(255) NULL, """
                '"verified_at" TIMESTAMP NULL, "created_at" DATETIME NULL DEFAULT CURRENT_TIMESTAMP, '
                '"updated_at" DATETIME NULL DEFAULT CURRENT_TIMESTAMP, '
                "UNIQUE(email), UNIQUE(email, name))"
            ],
        )

    async def test_can_create_indexes(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.query = MagicMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.index("name")
            blueprint.index("active", "active_idx")
            blueprint.index(["name", "email"])
            blueprint.unique("name")
            blueprint.unique(["name", "email"])
            blueprint.fulltext("description")

        self.assertEqual(len(blueprint.table.added_columns), 0)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE INDEX users_name_index ON "users"(name)',
                'CREATE INDEX active_idx ON "users"(active)',
                'CREATE INDEX users_name_email_index ON "users"(name,email)',
                'CREATE UNIQUE INDEX users_name_unique ON "users"(name)',
                'CREATE UNIQUE INDEX users_name_email_unique ON "users"(name,email)',
            ],
        )

    async def test_can_create_indexes_on_previous_column(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.query = MagicMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.string("email").index()
            blueprint.string("active").index(name="email_idx")

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'ALTER TABLE "users" ADD COLUMN "email" VARCHAR NOT NULL',
                'ALTER TABLE "users" ADD COLUMN "active" VARCHAR NOT NULL',
                'CREATE INDEX users_email_index ON "users"(email)',
                'CREATE INDEX email_idx ON "users"(active)',
            ],
        )

    async def test_can_have_composite_keys(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name").unique()
            blueprint.integer("age")
            blueprint.integer("profile_id")
            blueprint.primary(["name", "age"])

        self.assertEqual(len(blueprint.table.added_columns), 3)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "users" '
                '("name" VARCHAR(255) NOT NULL, '
                '"age" INTEGER NOT NULL, '
                '"profile_id" INTEGER NOT NULL, '
                "UNIQUE(name), "
                "CONSTRAINT users_name_age_primary PRIMARY KEY (name, age))"
            ],
        )

    async def test_can_have_column_primary_key(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.string("name").primary()
            blueprint.integer("age")
            blueprint.integer("profile_id")

        self.assertEqual(len(blueprint.table.added_columns), 3)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "users" '
                '("name" VARCHAR(255) NOT NULL, '
                '"age" INTEGER NOT NULL, '
                '"profile_id" INTEGER NOT NULL, '
                "CONSTRAINT users_name_primary PRIMARY KEY (name))"
            ],
        )

    async def test_can_advanced_table_creation2(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.big_increments("id")
            blueprint.string("name")
            blueprint.string("duration")
            blueprint.string("url")
            blueprint.json("payload")
            blueprint.year("birth")
            blueprint.inet("last_address").nullable()
            blueprint.cidr("route_origin").nullable()
            blueprint.macaddr("mac_address").nullable()
            blueprint.datetime("published_at")
            blueprint.time("wakeup_at")
            blueprint.string("thumbnail").nullable()
            blueprint.integer("premium")
            blueprint.integer("author_id").unsigned().nullable()
            blueprint.foreign("author_id").references("id").on("users").on_delete("set null")
            blueprint.text("description")
            blueprint.timestamps()

        self.assertEqual(len(blueprint.table.added_columns), 17)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'CREATE TABLE "users" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "name" VARCHAR(255) NOT NULL, "duration" VARCHAR(255) NOT NULL, '
                '"url" VARCHAR(255) NOT NULL, "payload" JSON NOT NULL, "birth" VARCHAR(4) NOT NULL, "last_address" VARCHAR(255) NULL, "route_origin" VARCHAR(255) NULL, "mac_address" VARCHAR(255) NULL, '
                '"published_at" DATETIME NOT NULL, "wakeup_at" TIME NOT NULL, "thumbnail" VARCHAR(255) NULL, "premium" INTEGER NOT NULL, "author_id" INTEGER UNSIGNED NULL, "description" TEXT NOT NULL, '
                '"created_at" DATETIME NULL DEFAULT CURRENT_TIMESTAMP, "updated_at" DATETIME NULL DEFAULT CURRENT_TIMESTAMP, '
                'CONSTRAINT users_author_id_foreign FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE SET NULL)'
            ],
        )

    async def test_id_column_uses_autoincrement_on_sqlite(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("posts") as blueprint:
            blueprint.id()
            blueprint.string("title")

        sql = await blueprint.to_sql()
        self.assertEqual(len(sql), 1)
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", sql[0])
        self.assertNotIn("CONSTRAINT posts_id_primary PRIMARY KEY", sql[0])

    async def test_has_table(self):
        mock_run = AsyncMock(return_value=MagicMock())
        self.schema.get_connection().run = mock_run

        await self.schema.has_table("users")

        sql, _ = mock_run.call_args[0]
        self.assertEqual(sql, "SELECT name FROM sqlite_master WHERE type='table' AND name='users'")

    async def test_can_truncate(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.truncate("users")

        sql, _ = mock_statement.call_args[0]
        self.assertEqual(sql, 'DELETE FROM "users"')

    async def test_can_rename_table(self):
        mock_run = AsyncMock()
        self.schema.get_connection().run = mock_run

        await self.schema.rename("users", "clients")

        sql, _ = mock_run.call_args[0]
        self.assertEqual(sql, 'ALTER TABLE "users" RENAME TO "clients"')

    async def test_can_drop_table_if_exists(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.drop_table_if_exists("users")

        sql, _ = mock_statement.call_args[0]
        self.assertEqual(sql, 'DROP TABLE IF EXISTS "users"')

    async def test_can_drop_table(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.drop_table("users")

        sql, _ = mock_statement.call_args[0]
        self.assertEqual(sql, 'DROP TABLE "users"')

    async def test_has_column(self):
        mock_select = AsyncMock(return_value=[])
        self.schema.get_connection().select = mock_select

        await self.schema.has_column("users", "name")

        sql, _ = mock_select.call_args[0]
        self.assertEqual(
            sql,
            "SELECT name FROM pragma_table_info('users') WHERE name='name'",
        )

    async def test_can_have_unsigned_columns(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.integer("profile_id").unsigned()
            blueprint.big_integer("big_profile_id").unsigned()
            blueprint.tiny_integer("tiny_profile_id").unsigned()
            blueprint.small_integer("small_profile_id").unsigned()
            blueprint.medium_integer("medium_profile_id").unsigned()

        self.assertEqual(
            await blueprint.to_sql(),
            [
                """CREATE TABLE "users" ("""
                """"profile_id" INTEGER UNSIGNED NOT NULL, """
                """"big_profile_id" BIGINT UNSIGNED NOT NULL, """
                """"tiny_profile_id" TINYINT UNSIGNED NOT NULL, """
                """"small_profile_id" SMALLINT UNSIGNED NOT NULL, """
                """"medium_profile_id" MEDIUMINT UNSIGNED NOT NULL)"""
            ],
        )

    async def test_can_enable_foreign_keys(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.enable_foreign_key_constraints()

        sql, _ = mock_statement.call_args[0]
        self.assertEqual(sql, "PRAGMA foreign_keys = ON")

    async def test_can_disable_foreign_keys(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.disable_foreign_key_constraints()

        sql, _ = mock_statement.call_args[0]
        self.assertEqual(sql, "PRAGMA foreign_keys = OFF")

    async def test_can_truncate_without_foreign_keys(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        await self.schema.truncate("users", foreign_keys=True)

        calls = [args[0] for args, _ in mock_statement.call_args_list]
        self.assertEqual(
            calls,
            [
                "PRAGMA foreign_keys = OFF",
                'DELETE FROM "users"',
                "PRAGMA foreign_keys = ON",
            ],
        )

    async def test_can_add_enum(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.create("users") as blueprint:
            blueprint.enum("status", ["active", "inactive"]).default("active")

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                "CREATE TABLE \"users\" (\"status\" VARCHAR(255) CHECK(status IN ('active', 'inactive')) NOT NULL DEFAULT 'active')"
            ],
        )

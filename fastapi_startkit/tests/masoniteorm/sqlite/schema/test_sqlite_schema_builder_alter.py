from unittest.mock import AsyncMock

from fastapi_startkit.masoniteorm.schema.Table import Table

from ..test_case import TestCase


class TestSQLiteSchemaBuilderAlter(TestCase):
    async def test_can_add_columns(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.string("name")
            blueprint.string("external_type").default("external")
            blueprint.integer("age")

        self.assertEqual(len(blueprint.table.added_columns), 3)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'ALTER TABLE "users" ADD COLUMN "name" VARCHAR NOT NULL',
                """ALTER TABLE "users" ADD COLUMN "external_type" VARCHAR NOT NULL DEFAULT 'external'""",
                'ALTER TABLE "users" ADD COLUMN "age" INTEGER NOT NULL',
            ],
        )

    async def test_can_add_constraints(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.unique("name", name="table_unique")

        self.assertEqual(len(blueprint.table.added_columns), 0)
        self.assertEqual(
            await blueprint.to_sql(),
            ['CREATE UNIQUE INDEX table_unique ON "users"(name)'],
        )

    async def test_alter_rename(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("post", "integer")

        async with await self.schema.table("users") as blueprint:
            blueprint.rename("post", "comment", "integer")
            blueprint.table.from_table = table

        self.assertEqual(
            await blueprint.to_sql(),
            [
                "CREATE TEMPORARY TABLE __temp__users AS SELECT post FROM users",
                'DROP TABLE "users"',
                'CREATE TABLE "users" ("comment" INTEGER NOT NULL)',
                'INSERT INTO "users" ("comment") SELECT post FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

    async def test_alter_drop(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("post", "string")
        table.add_column("name", "string")
        table.add_column("email", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.drop_column("post")
            blueprint.table.from_table = table

        self.assertEqual(
            await blueprint.to_sql(),
            [
                "CREATE TEMPORARY TABLE __temp__users AS SELECT name, email FROM users",
                'DROP TABLE "users"',
                'CREATE TABLE "users" ("name" VARCHAR NOT NULL, "email" VARCHAR NOT NULL)',
                'INSERT INTO "users" ("name", "email") SELECT name, email FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

    async def test_change(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("age", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.integer("age").change()
            blueprint.string("name")
            blueprint.table.from_table = table

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(len(blueprint.table.changed_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'ALTER TABLE "users" ADD COLUMN "name" VARCHAR NOT NULL',
                "CREATE TEMPORARY TABLE __temp__users AS SELECT age FROM users",
                'DROP TABLE "users"',
                'CREATE TABLE "users" ("age" INTEGER NOT NULL, "name" VARCHAR(255) NOT NULL)',
                'INSERT INTO "users" ("age") SELECT age FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

    async def test_drop_add_and_change(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("age", "string")
        table.add_column("email", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.integer("age").change()
            blueprint.string("name")
            blueprint.drop_column("email")
            blueprint.table.from_table = table

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(len(blueprint.table.changed_columns), 1)

    async def test_timestamp_alter_add_nullable_column(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("age", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.timestamp("due_date").nullable()
            blueprint.table.from_table = table

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            ['ALTER TABLE "users" ADD COLUMN "due_date" TIMESTAMP NULL'],
        )

    async def test_alter_drop_on_table_schema_table(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("table_schema") as blueprint:
            blueprint.drop_column("name")

        async with await self.schema.table("table_schema") as blueprint:
            blueprint.string("name").nullable()

    async def test_alter_add_primary(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.primary("playlist_id")

        self.assertEqual(
            await blueprint.to_sql(),
            ['ALTER TABLE "users" ADD CONSTRAINT users_playlist_id_primary PRIMARY KEY (playlist_id)'],
        )

    async def test_alter_add_column_and_foreign_key(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("age", "string")
        table.add_column("email", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.unsigned_integer("playlist_id").nullable()
            blueprint.foreign("playlist_id").references("id").on("playlists").on_delete("cascade").on_update("SET NULL")
            blueprint.table.from_table = table

        self.assertEqual(
            await blueprint.to_sql(),
            [
                'ALTER TABLE "users" ADD COLUMN "playlist_id" INTEGER UNSIGNED NULL REFERENCES "playlists"("id")',
                "CREATE TEMPORARY TABLE __temp__users AS SELECT age, email FROM users",
                'DROP TABLE "users"',
                'CREATE TABLE "users" ("age" VARCHAR NOT NULL, "email" VARCHAR NOT NULL, "playlist_id" INTEGER UNSIGNED NULL, '
                'CONSTRAINT users_playlist_id_foreign FOREIGN KEY ("playlist_id") REFERENCES "playlists"("id") ON DELETE CASCADE ON UPDATE SET NULL)',
                'INSERT INTO "users" ("age", "email") SELECT age, email FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

    async def test_alter_add_foreign_key_only(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        table = Table("users")
        table.add_column("age", "string")
        table.add_column("email", "string")

        async with await self.schema.table("users") as blueprint:
            blueprint.foreign("playlist_id").references("id").on("playlists").on_delete("cascade").on_update("set null")
            blueprint.table.from_table = table

        self.assertEqual(
            await blueprint.to_sql(),
            [
                "CREATE TEMPORARY TABLE __temp__users AS SELECT age, email FROM users",
                'DROP TABLE "users"',
                'CREATE TABLE "users" ("age" VARCHAR NOT NULL, "email" VARCHAR NOT NULL, '
                'CONSTRAINT users_playlist_id_foreign FOREIGN KEY ("playlist_id") REFERENCES "playlists"("id") ON DELETE CASCADE ON UPDATE SET NULL)',
                'INSERT INTO "users" ("age", "email") SELECT age, email FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

    async def test_can_add_column_enum(self):
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("users") as blueprint:
            blueprint.enum("status", ["active", "inactive"]).default("active")

        self.assertEqual(len(blueprint.table.added_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                "ALTER TABLE \"users\" ADD COLUMN \"status\" VARCHAR CHECK('status' IN('active', 'inactive')) NOT NULL DEFAULT 'active'"
            ],
        )

    async def test_add_nullable_columns_without_from_table(self):
        """Regression: adding nullable columns should use async get_current_schema,
        not connection.query() which takes no arguments."""
        mock_statement = AsyncMock()
        conn = self.schema.get_connection()
        conn.statement = mock_statement
        conn.select = AsyncMock(return_value=[])

        async with await self.schema.table("clients") as blueprint:
            blueprint.text("website").nullable()
            blueprint.text("linkedin_url").nullable()

        self.assertEqual(len(blueprint.table.added_columns), 2)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                'ALTER TABLE "clients" ADD COLUMN "website" TEXT NULL',
                'ALTER TABLE "clients" ADD COLUMN "linkedin_url" TEXT NULL',
            ],
        )

    async def test_can_change_column_enum(self):
        mock_statement = AsyncMock()
        self.schema.get_connection().statement = mock_statement

        async with await self.schema.table("users") as blueprint:
            blueprint.enum("status", ["active", "inactive"]).default("active").change()
            blueprint.table.from_table = Table("users")

        self.assertEqual(len(blueprint.table.changed_columns), 1)
        self.assertEqual(
            await blueprint.to_sql(),
            [
                "CREATE TEMPORARY TABLE __temp__users AS SELECT  FROM users",
                'DROP TABLE "users"',
                "CREATE TABLE \"users\" (\"status\" VARCHAR(255) CHECK(status IN ('active', 'inactive')) NOT NULL DEFAULT 'active')",
                'INSERT INTO "users" ("status") SELECT status FROM __temp__users',
                "DROP TABLE __temp__users",
            ],
        )

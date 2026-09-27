import asyncio
import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.DBMigrateCommand import DBMigrateCommand
from fastapi_startkit.masoniteorm.commands.MigrateFreshCommand import MigrateFreshCommand
from fastapi_startkit.masoniteorm.commands.MigrateRefreshCommand import MigrateRefreshCommand
from fastapi_startkit.masoniteorm.commands.MigrateResetCommand import MigrateResetCommand
from fastapi_startkit.masoniteorm.commands.MigrateRollbackCommand import MigrateRollbackCommand
from fastapi_startkit.masoniteorm.commands.MigrateStatusCommand import MigrateStatusCommand
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator
from fastapi_startkit.masoniteorm.models.MigrationModel import MigrationModel

from .fixtures.app import create_app, DB_PATH

CREATE_POSTS = "2026_01_01_000000_create_posts_table"
ADD_BODY_TO_POSTS = "2026_01_01_000001_add_body_to_posts_table"


class TestMigrateCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.schema = self.app.make("db").get_schema_builder()
        asyncio.run(self._reset_db())

    def tearDown(self):
        if DB_PATH.exists():
            DB_PATH.unlink()

    async def _reset_db(self):
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        for table in await schema.get_all_tables():
            if table.startswith("sqlite_"):
                continue
            await schema.drop_table_if_exists(table)

    async def _migrate(self):
        db = self.app.make("db")
        await db.clear()
        migrations_dir = self.app.use_base_path("databases/migrations")
        migrator = Migrator(
            connection="sqlite",
            migration_directory=migrations_dir,
        )
        await migrator.create_table_if_not_exists()
        await migrator.migrate()

    def _make_command(self, command_class):
        cmd = command_class()
        cmd.set_container(self.app)
        return cmd

    def _has_table(self, table):
        return asyncio.run(self.schema.has_table(table))

    def _has_column(self, table, column):
        return asyncio.run(self.schema.has_column(table, column))

    def _ran_migrations(self):
        return asyncio.run(self._fetch_ran_migrations())

    @staticmethod
    async def _fetch_ran_migrations():
        rows = await MigrationModel.all()
        return sorted((row.migration, row.batch) for row in rows)

    # -- behavior is proven by the real sqlite schema and the migrations
    # tracking table, not by console output --

    def test_migrate_creates_table_and_applies_pending_migrations(self):
        cmd = self._make_command(DBMigrateCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertTrue(self._has_table("posts"))
        self.assertTrue(self._has_column("posts", "title"))
        self.assertTrue(self._has_column("posts", "body"))
        self.assertEqual(
            self._ran_migrations(),
            [(CREATE_POSTS, 1), (ADD_BODY_TO_POSTS, 1)],
        )

    def test_migrate_is_idempotent_when_nothing_pending(self):
        cmd = self._make_command(DBMigrateCommand)
        CommandTester(cmd).execute("--connection sqlite")
        ran_after_first_run = self._ran_migrations()

        CommandTester(cmd).execute("--connection sqlite")

        self.assertEqual(self._ran_migrations(), ran_after_first_run)
        self.assertTrue(self._has_table("posts"))

    def test_status_command_creates_tracking_table_without_running_migrations(self):
        cmd = self._make_command(MigrateStatusCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertTrue(self._has_table("migrations"))
        self.assertFalse(self._has_table("posts"))
        self.assertEqual(self._ran_migrations(), [])

    def test_status_command_leaves_state_unchanged_after_migrate(self):
        asyncio.run(self._migrate())
        ran_before = self._ran_migrations()

        cmd = self._make_command(MigrateStatusCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertEqual(self._ran_migrations(), ran_before)
        self.assertTrue(self._has_table("posts"))

    def test_rollback_drops_last_batch(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateRollbackCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertEqual(self._ran_migrations(), [])
        self.assertFalse(self._has_table("posts"))

    def test_reset_rolls_back_all_migrations(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateResetCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertEqual(self._ran_migrations(), [])
        self.assertFalse(self._has_table("posts"))

    def test_refresh_resets_and_remigrates(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateRefreshCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertTrue(self._has_table("posts"))
        self.assertTrue(self._has_column("posts", "body"))
        self.assertEqual(
            self._ran_migrations(),
            [(CREATE_POSTS, 1), (ADD_BODY_TO_POSTS, 1)],
        )

    def test_fresh_drops_all_tables_and_remigrates(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateFreshCommand)
        CommandTester(cmd).execute("--connection sqlite")

        self.assertTrue(self._has_table("posts"))
        self.assertTrue(self._has_column("posts", "body"))
        self.assertEqual(
            self._ran_migrations(),
            [(CREATE_POSTS, 1), (ADD_BODY_TO_POSTS, 1)],
        )

    def test_migrate_command_reports_success_message(self):
        # Minimal, secondary output check -- the user-facing message contract,
        # not a substitute for the schema-state assertions above.
        cmd = self._make_command(DBMigrateCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")

        self.assertIn("Migrated:", tester.io.fetch_output())

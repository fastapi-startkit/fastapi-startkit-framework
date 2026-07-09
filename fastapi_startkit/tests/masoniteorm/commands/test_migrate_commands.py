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
from .fixtures.app import create_app, DB_PATH


class TestMigrateCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        asyncio.run(self._reset_db())

    def tearDown(self):
        if DB_PATH.exists():
            DB_PATH.unlink()

    async def _reset_db(self):
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        for table in await schema.get_all_tables():
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

    def test_migrate_runs_pending_migrations(self):
        cmd = self._make_command(DBMigrateCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Migrated:", output)
        self.assertIn("create_posts_table", output)

    def test_migrate_reports_nothing_to_migrate(self):
        cmd = self._make_command(DBMigrateCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        tester.io.fetch_output()

        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Nothing To Migrate!", output)

    def test_status_shows_unran_migrations(self):
        cmd = self._make_command(MigrateStatusCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("create_posts_table", output)
        self.assertIn("N", output)

    def test_status_shows_ran_migrations(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateStatusCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("create_posts_table", output)
        self.assertIn("Y", output)

    def test_rollback_rolls_back_last_batch(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateRollbackCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Rolled back:", output)
        self.assertIn("create_posts_table", output)

    def test_reset_rolls_back_all_migrations(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateResetCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Rolled back:", output)
        self.assertIn("create_posts_table", output)

    def test_refresh_resets_and_remigrates(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateRefreshCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Rolled back:", output)
        self.assertIn("Migrated:", output)
        self.assertIn("create_posts_table", output)

    def test_fresh_drops_all_tables_and_remigrates(self):
        asyncio.run(self._migrate())

        cmd = self._make_command(MigrateFreshCommand)
        tester = CommandTester(cmd)
        tester.execute("--connection sqlite")
        output = tester.io.fetch_output()
        self.assertIn("Dropping all tables", output)
        self.assertIn("Migrated:", output)
        self.assertIn("create_posts_table", output)

import asyncio
import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.DBSeedCommand import DBSeedCommand

from .fixtures.app import create_app, DB_PATH
from .fixtures.models import SeededUser

FIXTURE_SEED_PATH = "tests.masoniteorm.commands.fixtures.databases.seeders"


class TestDBSeedCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        asyncio.run(self._reset_table())

    def tearDown(self):
        asyncio.run(self._drop_table())
        if DB_PATH.exists():
            DB_PATH.unlink()

    async def _reset_table(self):
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        await schema.drop_table_if_exists("seed_users")
        async with await schema.create("seed_users") as table:
            table.id()
            table.string("name")

    async def _drop_table(self):
        db = self.app.make("db")
        schema = db.get_schema_builder()
        await schema.drop_table_if_exists("seed_users")
        await db.clear()

    def _run(self, args=""):
        tester = CommandTester(DBSeedCommand())
        tester.execute(args)
        return tester.io.fetch_output()

    def _seeded_names(self):
        return asyncio.run(self._fetch_names())

    @staticmethod
    async def _fetch_names():
        rows = await SeededUser.all()
        return sorted(row.name for row in rows)

    # -- behavior is proven by the rows the real Seeder + real fixture seeder
    # classes write into a real sqlite table, not by console output --

    def test_runs_database_seeder_by_default(self):
        self._run(f"--directory {FIXTURE_SEED_PATH} --connection sqlite")

        self.assertEqual(self._seeded_names(), ["database-seeder"])

    def test_seeds_specific_table_from_argument(self):
        self._run(f"user --directory {FIXTURE_SEED_PATH} --connection sqlite")

        self.assertEqual(self._seeded_names(), ["user-table-seeder"])

    def test_class_option_resolves_plain_class_name(self):
        self._run(f"--directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        self.assertEqual(self._seeded_names(), ["sample-seeder"])

    def test_class_option_resolves_table_seeder_suffix(self):
        self._run(f"--directory {FIXTURE_SEED_PATH} --class UserTableSeeder --connection sqlite")

        self.assertEqual(self._seeded_names(), ["user-table-seeder"])

    def test_class_option_accepts_dotted_path(self):
        self._run(f"--directory {FIXTURE_SEED_PATH} --class special_seeder.SpecialSeeder --connection sqlite")

        self.assertEqual(self._seeded_names(), ["special-seeder"])

    def test_class_option_takes_precedence_over_table_argument(self):
        self._run(f"user --directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        self.assertEqual(self._seeded_names(), ["sample-seeder"])

    def test_uses_default_connection_when_not_specified(self):
        self._run(f"--directory {FIXTURE_SEED_PATH}")

        self.assertEqual(self._seeded_names(), ["database-seeder"])

    def test_success_message_names_the_seeder(self):
        # Minimal, secondary output check -- the user-facing message contract,
        # not a substitute for the row assertions above.
        output = self._run(f"--directory {FIXTURE_SEED_PATH} --connection sqlite")

        self.assertIn("Database Seeder seeded!", output)

    # -- error paths: driven directly through CommandTester, since the console
    # application catches command exceptions instead of propagating them --

    def test_raises_when_seeder_class_cannot_be_found(self):
        with self.assertRaises(ValueError):
            self._run(f"--directory {FIXTURE_SEED_PATH} --class does_not_exist.NopeSeeder --connection sqlite")

    def test_raises_when_database_seeder_missing_from_directory(self):
        with self.assertRaises(ValueError):
            self._run("--directory tests.masoniteorm.commands.fixtures.databases.migrations --connection sqlite")

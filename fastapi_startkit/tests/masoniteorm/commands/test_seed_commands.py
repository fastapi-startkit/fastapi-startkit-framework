import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.DBSeedCommand import DBSeedCommand

from .fixtures.databases.seeders.recorder import CALLS

FIXTURE_SEED_PATH = "tests.masoniteorm.commands.fixtures.databases.seeders"


class TestDBSeedCommand(unittest.TestCase):
    def setUp(self):
        CALLS.clear()

    def tearDown(self):
        CALLS.clear()

    def _make_tester(self):
        command = DBSeedCommand()
        return CommandTester(command)

    def test_runs_database_seeder_by_default(self):
        tester = self._make_tester()
        tester.execute(f"--directory {FIXTURE_SEED_PATH} --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("Database Seeder seeded!", output)
        self.assertEqual(CALLS, [("database", "sqlite")])

    def test_runs_seeder_for_table_argument(self):
        tester = self._make_tester()
        tester.execute(f"user --directory {FIXTURE_SEED_PATH} --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("UserTableSeeder seeded!", output)
        self.assertEqual(CALLS, [("user_table", "sqlite")])

    def test_runs_seeder_for_class_option_without_table_suffix(self):
        tester = self._make_tester()
        tester.execute(f"--directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("SampleSeeder seeded!", output)
        self.assertEqual(CALLS, [("sample", "sqlite")])

    def test_runs_seeder_for_class_option_with_table_suffix(self):
        tester = self._make_tester()
        tester.execute(f"--directory {FIXTURE_SEED_PATH} --class UserTableSeeder --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("UserTableSeeder seeded!", output)
        self.assertEqual(CALLS, [("user_table", "sqlite")])

    def test_runs_seeder_for_fully_qualified_class_option(self):
        tester = self._make_tester()
        tester.execute(f"--directory {FIXTURE_SEED_PATH} --class special_seeder.SpecialSeeder --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("SpecialSeeder seeded!", output)
        self.assertEqual(CALLS, [("special", "sqlite")])

    def test_class_option_takes_precedence_over_table_argument(self):
        tester = self._make_tester()
        tester.execute(f"user --directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        output = tester.io.fetch_output()
        self.assertIn("SampleSeeder seeded!", output)
        self.assertEqual(CALLS, [("sample", "sqlite")])

    def test_raises_when_seeder_class_cannot_be_found(self):
        tester = self._make_tester()

        with self.assertRaises(ValueError):
            tester.execute(f"--directory {FIXTURE_SEED_PATH} --class does_not_exist.NopeSeeder --connection sqlite")

    def test_raises_when_database_seeder_missing_from_directory(self):
        tester = self._make_tester()

        with self.assertRaises(ValueError):
            tester.execute("--directory tests.masoniteorm.commands.fixtures.databases.migrations --connection sqlite")

    def test_uses_default_connection_option(self):
        tester = self._make_tester()
        tester.execute(f"--directory {FIXTURE_SEED_PATH}")

        self.assertEqual(CALLS, [("database", "default")])

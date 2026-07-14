import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.DBSeedCommand import DBSeedCommand

from .fixtures.databases.seeders.recorder import CALLS

FIXTURE_SEED_PATH = "tests.masoniteorm.commands.fixtures.databases.seeders"


class FakeSeeder:
    """Records constructor args and awaited methods, mocking DB side effects."""

    instances = []

    def __init__(self, seed_path="databases/seeders", connection=None):
        self.seed_path = seed_path
        self.connection = connection
        self.calls = []
        FakeSeeder.instances.append(self)

    async def run_database_seed(self):
        self.calls.append(("run_database_seed", None))

    async def run_specific_seed(self, seed):
        self.calls.append(("run_specific_seed", seed))


class TestDBSeedCommand(unittest.TestCase):
    def setUp(self):
        from .fixtures.app import create_app

        self.app = create_app()
        CALLS.clear()

    def tearDown(self):
        CALLS.clear()

    def _run(self, args=""):
        tester = CommandTester(DBSeedCommand())
        tester.execute(args)
        return tester.io.fetch_output()

    def _run_app(self, args=""):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.app.run("db:seed", args)
        return buffer.getvalue()

    # -- option/argument resolution, exercised against a mocked Seeder --

    def test_runs_database_seeder_by_default(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            output = self._run("")

        self.assertIn("Database Seeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.calls, [("run_database_seed", None)])
        self.assertEqual(seeder.seed_path, "databases/seeders")
        self.assertEqual(seeder.connection, "default")

    def test_seeds_specific_table_from_argument(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            output = self._run("posts")

        self.assertIn("PostsTableSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "posts_table_seeder.PostsTableSeeder")],
        )

    def test_class_option_resolves_plain_class_name(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            output = self._run("--class PostSeeder")

        self.assertIn("PostSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "post_seeder.PostSeeder")],
        )

    def test_class_option_resolves_table_seeder_suffix(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            output = self._run("--class PostTableSeeder")

        self.assertIn("PostTableSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "post_table_seeder.PostTableSeeder")],
        )

    def test_class_option_accepts_dotted_path(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            output = self._run("--class custom.MySeeder")

        self.assertIn("MySeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.calls, [("run_specific_seed", "custom.MySeeder")])

    def test_connection_and_directory_options_are_forwarded(self):
        FakeSeeder.instances = []
        with mock.patch("fastapi_startkit.masoniteorm.seeders.Seeder", FakeSeeder):
            self._run("--connection sqlite --directory db/seeds")

        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.seed_path, "db/seeds")
        self.assertEqual(seeder.connection, "sqlite")

    # -- end-to-end, driven through the registered console app against real fixture seeders --

    def test_runs_database_seeder_by_default_via_app(self):
        output = self._run_app(f"--directory {FIXTURE_SEED_PATH} --connection sqlite")

        self.assertIn("Database Seeder seeded!", output)
        self.assertEqual(CALLS, [("database", "sqlite")])

    def test_runs_seeder_for_table_argument_via_app(self):
        output = self._run_app(f"user --directory {FIXTURE_SEED_PATH} --connection sqlite")

        self.assertIn("UserTableSeeder seeded!", output)
        self.assertEqual(CALLS, [("user_table", "sqlite")])

    def test_runs_seeder_for_class_option_without_table_suffix_via_app(self):
        output = self._run_app(f"--directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        self.assertIn("SampleSeeder seeded!", output)
        self.assertEqual(CALLS, [("sample", "sqlite")])

    def test_runs_seeder_for_class_option_with_table_suffix_via_app(self):
        output = self._run_app(f"--directory {FIXTURE_SEED_PATH} --class UserTableSeeder --connection sqlite")

        self.assertIn("UserTableSeeder seeded!", output)
        self.assertEqual(CALLS, [("user_table", "sqlite")])

    def test_runs_seeder_for_fully_qualified_class_option_via_app(self):
        output = self._run_app(
            f"--directory {FIXTURE_SEED_PATH} --class special_seeder.SpecialSeeder --connection sqlite"
        )

        self.assertIn("SpecialSeeder seeded!", output)
        self.assertEqual(CALLS, [("special", "sqlite")])

    def test_class_option_takes_precedence_over_table_argument_via_app(self):
        output = self._run_app(f"user --directory {FIXTURE_SEED_PATH} --class SampleSeeder --connection sqlite")

        self.assertIn("SampleSeeder seeded!", output)
        self.assertEqual(CALLS, [("sample", "sqlite")])

    def test_uses_default_connection_option_via_app(self):
        self._run_app(f"--directory {FIXTURE_SEED_PATH}")

        self.assertEqual(CALLS, [("database", "default")])

    # -- error paths: driven directly through CommandTester, since the console
    # application catches command exceptions instead of propagating them --

    def test_raises_when_seeder_class_cannot_be_found(self):
        with self.assertRaises(ValueError):
            self._run(f"--directory {FIXTURE_SEED_PATH} --class does_not_exist.NopeSeeder --connection sqlite")

    def test_raises_when_database_seeder_missing_from_directory(self):
        with self.assertRaises(ValueError):
            self._run("--directory tests.masoniteorm.commands.fixtures.databases.migrations --connection sqlite")


if __name__ == "__main__":
    unittest.main()

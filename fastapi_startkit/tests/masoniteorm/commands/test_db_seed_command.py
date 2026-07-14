import unittest
from unittest import mock

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.DBSeedCommand import DBSeedCommand


class FakeSeeder:
    """Records constructor args and awaited methods, mocking DB side effects."""

    instances = []

    def __init__(self, seed_path="databases/seeds", connection=None):
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
        FakeSeeder.instances = []
        patcher = mock.patch(
            "fastapi_startkit.masoniteorm.seeders.Seeder",
            FakeSeeder,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, args=""):
        tester = CommandTester(DBSeedCommand())
        tester.execute(args)
        return tester.io.fetch_output()

    def test_runs_database_seeder_by_default(self):
        output = self._run("")

        self.assertIn("Database Seeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.calls, [("run_database_seed", None)])
        self.assertEqual(seeder.seed_path, "databases/seeders")
        self.assertEqual(seeder.connection, "default")

    def test_seeds_specific_table_from_argument(self):
        output = self._run("posts")

        self.assertIn("PostsTableSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "posts_table_seeder.PostsTableSeeder")],
        )

    def test_class_option_resolves_plain_class_name(self):
        output = self._run("--class PostSeeder")

        self.assertIn("PostSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "post_seeder.PostSeeder")],
        )

    def test_class_option_resolves_table_seeder_suffix(self):
        output = self._run("--class PostTableSeeder")

        self.assertIn("PostTableSeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(
            seeder.calls,
            [("run_specific_seed", "post_table_seeder.PostTableSeeder")],
        )

    def test_class_option_accepts_dotted_path(self):
        output = self._run("--class custom.MySeeder")

        self.assertIn("MySeeder seeded!", output)
        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.calls, [("run_specific_seed", "custom.MySeeder")])

    def test_connection_and_directory_options_are_forwarded(self):
        self._run("--connection sqlite --directory db/seeds")

        seeder = FakeSeeder.instances[-1]
        self.assertEqual(seeder.seed_path, "db/seeds")
        self.assertEqual(seeder.connection, "sqlite")


if __name__ == "__main__":
    unittest.main()

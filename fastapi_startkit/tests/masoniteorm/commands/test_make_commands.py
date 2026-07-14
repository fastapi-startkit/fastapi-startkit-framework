import os
import shutil
import tempfile
import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.MakeMigrationCommand import MakeMigrationCommand
from fastapi_startkit.masoniteorm.commands.MakeModelCommand import MakeModelCommand
from fastapi_startkit.masoniteorm.commands.MakeObserverCommand import MakeObserverCommand
from fastapi_startkit.masoniteorm.commands.MakeSeedCommand import MakeSeedCommand


class _TempCwdTestCase(unittest.TestCase):
    """Base case that runs each test inside an isolated temp working directory.

    The make/generator commands write files relative to ``os.getcwd()``, so the
    working directory is swapped for a throwaway one to keep the repo clean.
    """

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._tmp_dir = tempfile.mkdtemp()
        os.chdir(self._tmp_dir)

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _tester(self, command_class):
        return CommandTester(command_class())

    def _read_single_file(self, directory):
        files = [f for f in os.listdir(directory) if f.endswith(".py")]
        self.assertEqual(len(files), 1, f"expected one generated file in {directory}, got {files}")
        with open(os.path.join(directory, files[0])) as fp:
            return files[0], fp.read()


class TestMakeMigrationCommand(_TempCwdTestCase):
    def test_creates_migration_with_inferred_table(self):
        os.makedirs("databases/migrations")
        tester = self._tester(MakeMigrationCommand)
        tester.execute("create_posts_table")

        output = tester.io.fetch_output()
        self.assertIn("Migration file created:", output)

        file_name, content = self._read_single_file("databases/migrations")
        self.assertTrue(file_name.endswith("_create_posts_table.py"))
        self.assertIn("class CreatePostsTable(Migration)", content)
        self.assertIn('self.schema.create("posts")', content)

    def test_create_option_uses_create_stub(self):
        os.makedirs("databases/migrations")
        tester = self._tester(MakeMigrationCommand)
        tester.execute("add_users --create users")

        _, content = self._read_single_file("databases/migrations")
        self.assertIn('self.schema.create("users")', content)

    def test_table_option_uses_table_stub(self):
        os.makedirs("databases/migrations")
        tester = self._tester(MakeMigrationCommand)
        tester.execute("modify_users --table users")

        _, content = self._read_single_file("databases/migrations")
        self.assertIn('self.schema.table("users")', content)
        self.assertNotIn("self.schema.create", content)

    def test_custom_directory_option(self):
        os.makedirs("custom/migrations")
        tester = self._tester(MakeMigrationCommand)
        tester.execute("create_posts_table --directory custom/migrations")

        output = tester.io.fetch_output()
        self.assertIn("custom/migrations", output)
        self.assertTrue(any(f.endswith(".py") for f in os.listdir("custom/migrations")))


class TestMakeModelCommand(_TempCwdTestCase):
    def test_creates_model_file(self):
        os.makedirs("app")
        tester = self._tester(MakeModelCommand)
        tester.execute("Post")

        output = tester.io.fetch_output()
        self.assertIn("Model created:", output)

        content = open(os.path.join("app", "Post.py")).read()
        self.assertIn("class Post(Model)", content)

    def test_pep_option_uses_underscore_filename(self):
        os.makedirs("app")
        tester = self._tester(MakeModelCommand)
        tester.execute("BlogPost --pep")

        self.assertTrue(os.path.exists(os.path.join("app", "blog_post.py")))

    def test_reports_when_model_already_exists(self):
        os.makedirs("app")
        self._tester(MakeModelCommand).execute("Post")

        tester = self._tester(MakeModelCommand)
        tester.execute("Post")
        output = tester.io.fetch_output()
        self.assertIn('Model "Post" Already Exists', output)

    def test_custom_directory_option(self):
        os.makedirs("models")
        tester = self._tester(MakeModelCommand)
        tester.execute("Post --directory models")

        self.assertTrue(os.path.exists(os.path.join("models", "Post.py")))


class TestMakeSeedCommand(_TempCwdTestCase):
    def test_creates_seed_file(self):
        os.makedirs("databases/seeders")
        tester = self._tester(MakeSeedCommand)
        tester.execute("Post")

        output = tester.io.fetch_output()
        self.assertIn("Seed file created:", output)

        content = open(os.path.join("databases/seeders", "post_table_seeder.py")).read()
        self.assertIn("class PostTableSeeder(Seeder)", content)

    def test_reports_when_seed_already_exists(self):
        os.makedirs("databases/seeders")
        self._tester(MakeSeedCommand).execute("Post")

        tester = self._tester(MakeSeedCommand)
        tester.execute("Post")
        output = tester.io.fetch_output()
        self.assertIn("already exists.", output)


class TestMakeObserverCommand(_TempCwdTestCase):
    def test_creates_observer_file(self):
        tester = self._tester(MakeObserverCommand)
        tester.execute("Post")

        output = tester.io.fetch_output()
        self.assertIn("Observer created:", output)

        content = open(os.path.join("app/observers", "PostObserver.py")).read()
        self.assertIn("class PostObserver:", content)
        self.assertIn("def created(self, post):", content)

    def test_model_option_controls_variable_and_type(self):
        tester = self._tester(MakeObserverCommand)
        tester.execute("Audit --model User")

        content = open(os.path.join("app/observers", "AuditObserver.py")).read()
        self.assertIn("class AuditObserver:", content)
        self.assertIn("def created(self, user):", content)
        self.assertIn("User model.", content)

    def test_reports_when_observer_already_exists(self):
        self._tester(MakeObserverCommand).execute("Post")

        tester = self._tester(MakeObserverCommand)
        tester.execute("Post")
        output = tester.io.fetch_output()
        self.assertIn('Observer "Post" Already Exists', output)


if __name__ == "__main__":
    unittest.main()

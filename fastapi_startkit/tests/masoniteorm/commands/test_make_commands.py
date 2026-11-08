import asyncio
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.MakeMigrationCommand import MakeMigrationCommand
from fastapi_startkit.masoniteorm.commands.MakeModelCommand import MakeModelCommand
from fastapi_startkit.masoniteorm.commands.MakeObserverCommand import MakeObserverCommand
from fastapi_startkit.masoniteorm.commands.MakeSeedCommand import MakeSeedCommand
from fastapi_startkit.masoniteorm.migrations.Migration import Migration
from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm.seeders import Seeder

from .fixtures.app import create_app, DB_PATH


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

    def _load_class(self, path, class_name):
        spec = importlib.util.spec_from_file_location(class_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, class_name)

    def _generated_file(self, directory):
        files = [f for f in os.listdir(directory) if f.endswith(".py")]
        self.assertEqual(len(files), 1, f"expected one generated file in {directory}, got {files}")
        return os.path.join(directory, files[0])

    def _read_single_file(self, directory):
        path = self._generated_file(directory)
        with open(path) as fp:
            return os.path.basename(path), fp.read()


class TestMakeMigrationCommand(_TempCwdTestCase):
    """Real sqlite integration tests: a generated migration is actually executed
    against a live sqlite database and the resulting schema is inspected, rather
    than asserting on the generated file's text.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        super().setUp()
        asyncio.run(self._reset_db())

    def tearDown(self):
        super().tearDown()
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

    def _generate(self, args, directory="databases/migrations"):
        os.makedirs(directory, exist_ok=True)
        tester = self._tester(MakeMigrationCommand)
        tester.execute(args)
        return self._generated_file(directory), tester.io.fetch_output()

    @staticmethod
    def _load_migration_class(file_path):
        spec = importlib.util.spec_from_file_location(
            f"generated_migration_{os.path.basename(file_path).replace('.py', '')}",
            file_path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, Migration) and obj is not Migration:
                return obj
        raise AssertionError(f"no Migration subclass found in {file_path}")

    def _run_generated_migration(self, file_path):
        asyncio.run(self._execute_up(file_path))

    async def _execute_up(self, file_path):
        migration_class = self._load_migration_class(file_path)
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        await migration_class(connection="sqlite", schema=schema).up()

    async def _create_table(self, name):
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        async with await schema.create(name) as table:
            table.increments("id")

    def _has_table(self, table):
        return asyncio.run(self._async_has_table(table))

    async def _async_has_table(self, table):
        db = self.app.make("db")
        await db.clear()
        return await db.get_schema_builder().has_table(table)

    def _has_column(self, table, column):
        return asyncio.run(self._async_has_column(table, column))

    async def _async_has_column(self, table, column):
        db = self.app.make("db")
        await db.clear()
        return await db.get_schema_builder().has_column(table, column)

    # -- behavior is proven by the real sqlite schema the generated migration
    # produces when executed, not by the generated file's text --

    def test_inferred_table_migration_creates_real_table(self):
        file_path, output = self._generate("create_posts_table")
        self.assertIn("Migration file created:", output)

        self.assertFalse(self._has_table("posts"))
        self._run_generated_migration(file_path)

        self.assertTrue(self._has_table("posts"))
        self.assertTrue(self._has_column("posts", "id"))
        self.assertTrue(self._has_column("posts", "created_at"))
        self.assertTrue(self._has_column("posts", "updated_at"))

    def test_create_option_creates_named_table(self):
        file_path, _ = self._generate("add_users --create users")

        self._run_generated_migration(file_path)

        self.assertTrue(self._has_table("users"))
        self.assertTrue(self._has_column("users", "id"))

    def test_table_option_migration_executes_against_existing_table(self):
        # The table (alter) stub has an empty ``up`` body, so there is no new
        # column to assert -- the meaningful real-DB check is that the generated
        # alter migration executes cleanly against an existing table.
        asyncio.run(self._create_table("widgets"))
        file_path, _ = self._generate("modify_widgets --table widgets")

        self._run_generated_migration(file_path)

        self.assertTrue(self._has_table("widgets"))

    def test_custom_directory_migration_runs_from_custom_location(self):
        file_path, output = self._generate(
            "create_posts_table --directory custom/migrations",
            directory="custom/migrations",
        )
        self.assertIn("custom/migrations", output)

        self._run_generated_migration(file_path)

        self.assertTrue(self._has_table("posts"))


class TestMakeModelCommand(_TempCwdTestCase):
    # make:model emits a plain Python class with no schema side effects, so
    # there is nothing to run against a database -- the generated file content
    # is the only meaningful contract to assert.
    def test_creates_model_file(self):
        tester = self._tester(MakeModelCommand)
        tester.execute("Post")

        output = tester.io.fetch_output()
        self.assertIn("Model created:", output)

        content = open(os.path.join("app/models", "Post.py")).read()
        self.assertIn("class Post(Model)", content)

    def test_generated_model_imports(self):
        self._tester(MakeModelCommand).execute("Post")

        content = open(os.path.join("app/models", "Post.py")).read()
        self.assertIn("from fastapi_startkit.masoniteorm.models import Model", content)
        self.assertNotIn('"""', content)

        post_class = self._load_class(os.path.join("app/models", "Post.py"), "Post")
        self.assertTrue(issubclass(post_class, Model))

    def test_migration_option_creates_migration_through_console(self):
        app = create_app()

        self.assertEqual(app.run("db:make:model", "Post --migration"), 0)

        migration = self._generated_file("databases/migrations")
        self.assertTrue(migration.endswith("_create_posts_table.py"))
        content = open(migration).read()
        self.assertIn('self.schema.create("posts")', content)

    def test_migration_and_table_options_create_update_migration_through_console(self):
        app = create_app()

        self.assertEqual(app.run("db:make:model", "Post --migration --table"), 0)

        migration = self._generated_file("databases/migrations")
        self.assertTrue(migration.endswith("_update_posts_table.py"))
        content = open(migration).read()
        self.assertIn('self.schema.table("posts")', content)

    def test_seeder_option_creates_seeder_through_console(self):
        app = create_app()

        self.assertEqual(app.run("db:make:model", "Post --seeder"), 0)

        self.assertTrue(os.path.exists(os.path.join("databases/seeders", "post_table_seeder.py")))

    def test_pep_option_uses_underscore_filename(self):
        tester = self._tester(MakeModelCommand)
        tester.execute("BlogPost --pep")

        self.assertTrue(os.path.exists(os.path.join("app/models", "blog_post.py")))

    def test_reports_when_model_already_exists(self):
        self._tester(MakeModelCommand).execute("Post")

        tester = self._tester(MakeModelCommand)
        tester.execute("Post")
        output = tester.io.fetch_output()
        self.assertIn('Model "Post" Already Exists', output)

    def test_custom_directory_option(self):
        tester = self._tester(MakeModelCommand)
        tester.execute("Post --directory models")

        self.assertTrue(os.path.exists(os.path.join("models", "Post.py")))

    def test_generated_model_resolves_through_the_package_import(self):
        self._tester(MakeModelCommand).execute("Post")

        content = open(os.path.join("app/models", "Post.py")).read()
        self.assertNotIn("from masoniteorm", content)
        self.assertTrue(issubclass(self._load_class(os.path.join("app/models", "Post.py"), "Post"), Model))


class TestMakeSeedCommand(_TempCwdTestCase):
    # make:seed emits a Seeder subclass with an empty ``run`` body; it performs
    # no database work on its own, so the generated file content is the only
    # meaningful contract (seeders executing against a real DB are covered in
    # test_db_seed_command.py).
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

    def test_generated_seeder_runs_through_seeding_path(self):
        os.makedirs("generated_seeds/seeders")
        self._tester(MakeSeedCommand).execute("Post --directory generated_seeds/seeders")

        content = open(os.path.join("generated_seeds/seeders", "post_table_seeder.py")).read()
        self.assertIn("from fastapi_startkit.masoniteorm.seeders import Seeder", content)
        self.assertIn("async def run(self) -> None:", content)
        self.assertNotIn('"""', content)

        sys.path.insert(0, self._tmp_dir)
        self.addCleanup(sys.path.remove, self._tmp_dir)
        self.addCleanup(self._forget_modules, "generated_seeds")

        seeder = Seeder(seed_path="generated_seeds/seeders")
        asyncio.run(seeder.run_specific_seed("post_table_seeder.PostTableSeeder"))

        self.assertEqual([seed.__name__ for seed in seeder.ran_seeds], ["PostTableSeeder"])

    @staticmethod
    def _forget_modules(package):
        for name in [name for name in sys.modules if name == package or name.startswith(f"{package}.")]:
            del sys.modules[name]


class TestMakeObserverCommand(_TempCwdTestCase):
    LIFECYCLE_EVENTS = ["saving", "creating", "updating", "created", "updated", "saved", "deleting", "deleted"]

    def test_creates_observer_file(self):
        tester = self._tester(MakeObserverCommand)
        tester.execute("Post")

        output = tester.io.fetch_output()
        self.assertIn("Observer created:", output)

        content = open(os.path.join("app/observers", "PostObserver.py")).read()
        self.assertIn("from fastapi_startkit.masoniteorm.models import Model", content)
        self.assertIn("class PostObserver:", content)
        self.assertIn("async def created(self, post: Model) -> None:", content)
        self.assertNotIn('"""', content)
        self.assertNotIn("#", content)

    def test_model_option_controls_variable_name(self):
        tester = self._tester(MakeObserverCommand)
        tester.execute("Audit --model User")

        content = open(os.path.join("app/observers", "AuditObserver.py")).read()
        self.assertIn("class AuditObserver:", content)
        self.assertIn("async def created(self, user: Model) -> None:", content)

    def test_generated_observer_imports_and_handles_lifecycle_events(self):
        self._tester(MakeObserverCommand).execute("Post")

        observer_class = self._load_class(os.path.join("app/observers", "PostObserver.py"), "PostObserver")
        handlers = [name for name in vars(observer_class) if not name.startswith("_")]
        self.assertEqual(handlers, self.LIFECYCLE_EVENTS)

        class Post(Model):
            __observers__ = {}

        Post.observe(observer_class())
        post = Post()
        for event in self.LIFECYCLE_EVENTS:
            asyncio.run(post.observe_events(post, event))

    def test_runs_through_console_as_db_make_observer(self):
        app = create_app()

        self.assertEqual(app.run("db:make:observer", "Order"), 0)
        self.assertTrue(os.path.exists(os.path.join("app/observers", "OrderObserver.py")))

    def test_reports_when_observer_already_exists(self):
        self._tester(MakeObserverCommand).execute("Post")

        tester = self._tester(MakeObserverCommand)
        tester.execute("Post")
        output = tester.io.fetch_output()
        self.assertIn('Observer "Post" Already Exists', output)


if __name__ == "__main__":
    unittest.main()

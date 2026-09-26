import asyncio
import unittest

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands.MakeModelDocstringCommand import MakeModelDocstringCommand

from .fixtures.app import create_app, DB_PATH


class TestMakeModelDocstringCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        asyncio.run(self._create_table())

    def tearDown(self):
        asyncio.run(self._drop_table())
        if DB_PATH.exists():
            DB_PATH.unlink()

    async def _create_table(self):
        db = self.app.make("db")
        await db.clear()
        schema = db.get_schema_builder()
        await schema.drop_table_if_exists("articles")
        async with await schema.create("articles") as table:
            table.increments("id")
            table.string("title", 120)
            table.integer("views").default(0)

    async def _drop_table(self):
        db = self.app.make("db")
        await db.get_schema_builder().drop_table_if_exists("articles")
        await db.clear()

    def _run(self, args: str) -> tuple[int, str, str]:
        command = MakeModelDocstringCommand()
        command.set_container(self.app)
        tester = CommandTester(command)
        status = tester.execute(args)
        return status, tester.io.fetch_output(), tester.io.fetch_error()

    def test_prints_docstring_from_the_live_table_schema(self):
        status, output, _ = self._run("articles")

        self.assertEqual(status, 0)
        self.assertIn("Model Docstring for table: articles", output)
        self.assertIn('"""\nid: ', output)
        self.assertIn("title: string(120)\n", output)
        self.assertRegex(output, r"\nviews: \w+ default: 0\n")
        self.assertNotIn("Model Type Hints", output)

    def test_type_hints_option_prints_python_types(self):
        status, output, _ = self._run("articles --type-hints --connection sqlite")

        self.assertEqual(status, 0)
        self.assertIn("Model Type Hints for table: articles", output)
        self.assertIn("    id: int\n", output)
        self.assertIn("    title: str\n", output)
        self.assertIn("    views: int\n", output)

    def test_missing_table_reports_error_and_fails(self):
        status, output, error = self._run("missing_table")

        self.assertEqual(status, 1)
        self.assertIn("There is no such table missing_table for this connection.", error)
        self.assertNotIn('"""', output)

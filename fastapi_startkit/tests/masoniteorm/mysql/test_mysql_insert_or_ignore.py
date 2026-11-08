from fastapi_startkit.masoniteorm import Model

from .fixtures.db import DB
from .test_case import TestCase

KEY = ["slug", "language"]


class IoLexeme(Model):
    __table__ = "io_lexemes"
    __timestamps__ = None
    id: int
    slug: str
    language: str
    word: str
    note: str


class TestMySQLInsertOrIgnore(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.schema = DB.get_schema_builder()
        await self.schema.drop_table_if_exists("io_lexemes")
        async with await self.schema.create("io_lexemes") as table:
            table.increments("id")
            table.string("slug")
            table.string("language")
            table.string("word")
            table.string("note").nullable()
            table.unique(KEY)

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("io_lexemes")
        await super().asyncTearDown()

    async def test_insert_or_ignore_keeps_the_first_row_for_a_key(self):
        self.assertEqual(await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "chat"}, KEY), 1)
        self.assertEqual(await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "matou"}, KEY), 0)

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([row.word for row in rows], ["chat"])

    async def test_upsert_inserts_then_updates_the_named_columns(self):
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "chat"}, KEY)
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "matou"}, KEY, ["word"])

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([row.word for row in rows], ["matou"])

    async def test_upsert_leaves_columns_outside_update_untouched(self):
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "chat", "note": "first"}, KEY)
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "matou", "note": "second"}, KEY, ["word"])

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([(row.word, row.note) for row in rows], [("matou", "first")])

    async def test_upsert_counts_follow_found_rows(self):
        row = {"slug": "chat", "language": "fr", "word": "chat"}
        self.assertEqual(await IoLexeme.upsert(row, KEY), 1)
        self.assertEqual(await IoLexeme.upsert({**row, "word": "matou"}, KEY), 2)
        self.assertEqual(await IoLexeme.upsert({**row, "word": "matou"}, KEY), 1)

import asyncio
import contextlib

from fastapi_startkit.masoniteorm import Model

from .fixtures.db import DB, schema
from .test_case import TestCase

BLOCKED_FOR = 0.3
SETTLES_WITHIN = 5
KEY = ["slug", "language"]


class IoLexeme(Model):
    __table__ = "io_lexemes"
    __timestamps__ = None
    id: int
    slug: str
    language: str
    word: str


class TestPostgresInsertOrIgnore(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.release = asyncio.Event()
        self.tasks = []
        await schema.drop_table_if_exists("io_lexemes")
        async with await schema.create("io_lexemes") as table:
            table.increments("id")
            table.string("slug")
            table.string("language")
            table.string("word")
            table.unique(KEY)

    async def asyncTearDown(self):
        self.release.set()
        for task in self.tasks:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(task, SETTLES_WITHIN)
        await schema.drop_table_if_exists("io_lexemes")
        await super().asyncTearDown()

    async def test_insert_or_ignore_keeps_the_first_row_for_a_key(self):
        self.assertEqual(await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "chat"}, KEY), 1)
        self.assertEqual(await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "matou"}, KEY), 0)

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([row.word for row in rows], ["chat"])

    async def test_insert_or_ignore_inserts_only_the_new_rows_of_a_batch(self):
        await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "chat"}, KEY)

        inserted = await IoLexeme.insert_or_ignore(
            [
                {"slug": "chat", "language": "fr", "word": "matou"},
                {"slug": "chat", "language": "en", "word": "cat"},
            ],
            KEY,
        )

        self.assertEqual(inserted, 1)
        self.assertEqual(await IoLexeme.query().count(), 2)

    async def test_upsert_inserts_then_updates_the_named_columns(self):
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "chat"}, KEY)
        await IoLexeme.upsert({"slug": "chat", "language": "fr", "word": "matou"}, KEY, ["word"])

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([row.word for row in rows], ["matou"])

    async def test_concurrent_insert_or_ignore_waits_and_leaves_one_row(self):
        held = asyncio.Event()

        async def first_writer():
            async with DB.connection().transaction():
                await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "first"}, KEY)
                held.set()
                await self.release.wait()

        async def second_writer():
            async with DB.connection().transaction():
                return await IoLexeme.insert_or_ignore({"slug": "chat", "language": "fr", "word": "second"}, KEY)

        self.tasks.append(asyncio.ensure_future(first_writer()))
        await asyncio.wait_for(held.wait(), SETTLES_WITHIN)

        second = asyncio.ensure_future(second_writer())
        self.tasks.append(second)
        done, _ = await asyncio.wait({second}, timeout=BLOCKED_FOR)
        self.assertEqual(done, set())

        self.release.set()
        self.assertEqual(await asyncio.wait_for(second, SETTLES_WITHIN), 0)

        rows = await IoLexeme.where("slug", "chat").get()
        self.assertEqual([row.word for row in rows], ["first"])

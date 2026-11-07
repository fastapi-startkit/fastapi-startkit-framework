from unittest.mock import patch

import pytest
from fastapi import FastAPI

from fastapi_startkit.masoniteorm.models.MigrationModel import MigrationModel
from fastapi_startkit.masoniteorm.testing import DatabaseTruncation
from fastapi_startkit.playwright import BrowserTestCase
from fastapi_startkit.testing.test_case import TestCase

from ..commands.fixtures.app import DB_PATH, create_app
from ..commands.fixtures.models import SeededUser

SEED_PATH = "tests.masoniteorm.commands.fixtures.databases.seeders"


class Truncation(DatabaseTruncation):
    migration_directory = "databases/seed_migrations"
    seed_directory = SEED_PATH


@pytest.fixture(scope="module", autouse=True)
def application():
    app = create_app()
    yield app
    if DB_PATH.exists():
        DB_PATH.unlink()


async def clear_connections() -> None:
    from fastapi_startkit.application import app

    await app().make("db").clear()


async def names() -> list[str]:
    return sorted(row.name for row in await SeededUser.all())


async def migrations() -> list[str]:
    return [row.migration for row in await MigrationModel.all()]


async def create_notes_table(schema) -> None:
    await schema.drop_table_if_exists("notes")
    async with await schema.create("notes") as table:
        table.id()
        table.string("body")


async def count(schema, table: str) -> int:
    rows = await schema.get_connection().select(f"SELECT COUNT(*) AS total FROM {table}")
    return rows[0]["total"]


class TestTruncateDatabase:
    @pytest.fixture(autouse=True)
    async def reset(self, application):
        with patch.object(DatabaseTruncation, "migrated", False):
            yield
        await application.make("db").clear()

    @pytest.fixture
    def schema(self, application):
        return application.make("db").get_schema_builder()

    async def test_first_call_migrates_fresh_and_seeds(self):
        await Truncation().truncate_database()

        assert DatabaseTruncation.migrated is True
        assert await migrations() == ["2026_01_01_000000_create_seed_users_table"]
        assert await names() == ["database-seeder"]

    async def test_later_calls_empty_tables_but_keep_migrations(self, schema):
        await Truncation().truncate_database()
        await SeededUser.create({"name": "left-over"})
        await create_notes_table(schema)
        await schema.get_connection().statement("INSERT INTO notes (body) VALUES ('left-over')")

        await Truncation().truncate_database()

        assert await names() == ["database-seeder"]
        assert await count(schema, "notes") == 0
        assert await migrations() == ["2026_01_01_000000_create_seed_users_table"]

    async def test_except_tables_are_kept(self, schema):
        class KeepNotes(Truncation):
            except_tables = ["notes"]

        await KeepNotes().truncate_database()
        await create_notes_table(schema)
        await schema.get_connection().statement("INSERT INTO notes (body) VALUES ('kept')")

        await KeepNotes().truncate_database()

        assert await count(schema, "notes") == 1
        assert await names() == ["database-seeder"]

    async def test_tables_to_truncate_limits_the_reset(self, schema):
        class OnlyNotes(Truncation):
            tables_to_truncate = ["notes"]
            seed = False

        await OnlyNotes().truncate_database()
        await SeededUser.create({"name": "kept"})
        await create_notes_table(schema)
        await schema.get_connection().statement("INSERT INTO notes (body) VALUES ('removed')")

        await OnlyNotes().truncate_database()

        assert await count(schema, "notes") == 0
        assert await names() == ["kept"]

    async def test_seeder_selects_the_seeder(self):
        class Special(Truncation):
            seeder = "SpecialSeeder"

        await Special().truncate_database()

        assert await names() == ["special-seeder"]

    async def test_seeding_can_be_turned_off(self):
        class Unseeded(Truncation):
            seed = False

        await Unseeded().truncate_database()

        assert await names() == []


class TestTruncationInTestCase(Truncation, TestCase):
    def get_application(self):
        return create_app()

    async def asyncStopTestRun(self):
        await clear_connections()

    async def test_resets_in_the_test_loop(self):
        await SeededUser.create({"name": "created-in-test"})

        assert await names() == ["created-in-test", "database-seeder"]


class TestTruncationInBrowserTestCase(Truncation, BrowserTestCase):
    def get_application(self):
        return FastAPI()

    async def asyncStopTestRun(self):
        await clear_connections()

    async def test_first_visit_sees_a_seeded_database(self):
        assert await names() == ["database-seeder"]
        await SeededUser.create({"name": "browser"})

    async def test_next_visit_sees_a_reset_database(self):
        assert await names() == ["database-seeder"]

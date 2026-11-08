import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar

GRAMMARS = {
    "sqlite": SQLiteGrammar,
    "mysql": MySQLGrammar,
    "postgres": PostgresGrammar,
}

EXPECTED = {
    "sqlite": {
        "ignore_keys": 'INSERT INTO "lexemes" ("slug", "language") VALUES (?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "ignore": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "ignore_any": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT DO NOTHING',
        "ignore_many": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?), (?, ?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "upsert": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT ("slug", "language") DO UPDATE SET "word" = EXCLUDED."word"',
    },
    "postgres": {
        "ignore_keys": 'INSERT INTO "lexemes" ("slug", "language") VALUES (?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "ignore": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "ignore_any": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT DO NOTHING',
        "ignore_many": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?), (?, ?, ?) ON CONFLICT ("slug", "language") DO NOTHING',
        "upsert": 'INSERT INTO "lexemes" ("slug", "language", "word") VALUES (?, ?, ?) ON CONFLICT ("slug", "language") DO UPDATE SET "word" = EXCLUDED."word"',
    },
    "mysql": {
        "ignore_keys": "INSERT IGNORE INTO `lexemes` (`slug`, `language`) VALUES (?, ?)",
        "ignore": "INSERT IGNORE INTO `lexemes` (`slug`, `language`, `word`) VALUES (?, ?, ?)",
        "ignore_any": "INSERT IGNORE INTO `lexemes` (`slug`, `language`, `word`) VALUES (?, ?, ?)",
        "ignore_many": "INSERT IGNORE INTO `lexemes` (`slug`, `language`, `word`) VALUES (?, ?, ?), (?, ?, ?)",
        "upsert": "INSERT INTO `lexemes` (`slug`, `language`, `word`) VALUES (?, ?, ?) ON DUPLICATE KEY UPDATE `word` = VALUES(`word`)",
    },
}

ROW = {"slug": "chat", "language": "fr", "word": "chat"}


class RecordingConnection:
    def __init__(self, grammar):
        self.grammar = grammar
        self.calls = []

    def query(self):
        return QueryBuilder(connection=self, grammar=self.grammar, processor=None).table("lexemes")

    async def affecting_statement(self, sql, bindings):
        self.calls.append((sql, bindings))
        return 1


class TestInsertOrIgnoreGrammar(unittest.IsolatedAsyncioTestCase):
    async def test_insert_or_ignore_targets_the_unique_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().insert_or_ignore(ROW, ["slug", "language"])
                self.assertEqual(connection.calls, [(EXPECTED[name]["ignore"], ["chat", "fr", "chat"])])

    async def test_insert_or_ignore_without_unique_columns_ignores_any_conflict(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().insert_or_ignore(ROW)
                self.assertEqual(connection.calls, [(EXPECTED[name]["ignore_any"], ["chat", "fr", "chat"])])

    async def test_insert_or_ignore_binds_every_row_in_the_first_rows_column_order(self):
        rows = [ROW, {"word": "chien", "language": "fr", "slug": "chien"}]
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().insert_or_ignore(rows, ["slug", "language"])
                self.assertEqual(
                    connection.calls,
                    [(EXPECTED[name]["ignore_many"], ["chat", "fr", "chat", "chien", "fr", "chien"])],
                )

    async def test_upsert_updates_the_columns_outside_the_unique_key_by_default(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().upsert(ROW, ["slug", "language"])
                self.assertEqual(connection.calls, [(EXPECTED[name]["upsert"], ["chat", "fr", "chat"])])

    async def test_upsert_updates_only_the_named_columns(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().upsert(ROW, ["slug", "language"], "word")
                self.assertEqual(connection.calls, [(EXPECTED[name]["upsert"], ["chat", "fr", "chat"])])

    async def test_upsert_with_nothing_to_update_inserts_or_ignores(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                connection = RecordingConnection(grammar)
                await connection.query().upsert({"slug": "chat", "language": "fr"}, ["slug", "language"])
                self.assertEqual(connection.calls, [(EXPECTED[name]["ignore_keys"], ["chat", "fr"])])

    async def test_empty_values_run_nothing(self):
        connection = RecordingConnection(PostgresGrammar)
        self.assertEqual(await connection.query().insert_or_ignore([]), 0)
        self.assertEqual(await connection.query().upsert([], "slug"), 0)
        self.assertEqual(connection.calls, [])

    async def test_upsert_needs_a_unique_column(self):
        connection = RecordingConnection(PostgresGrammar)
        with self.assertRaises(ValueError):
            await connection.query().upsert(ROW, [])

    async def test_mssql_refuses_both(self):
        connection = RecordingConnection(MSSQLGrammar)
        with self.assertRaises(NotImplementedError):
            await connection.query().insert_or_ignore(ROW, "slug")
        with self.assertRaises(NotImplementedError):
            await connection.query().upsert(ROW, "slug")
        self.assertEqual(connection.calls, [])

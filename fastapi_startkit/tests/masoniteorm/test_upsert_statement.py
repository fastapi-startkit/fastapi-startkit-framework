from unittest import TestCase

from sqlalchemy.dialects import mysql, postgresql, sqlite

from fastapi_startkit.masoniteorm.query.upsert import build_upsert_statement

ROWS = [
    {"email": "a@a.com", "name": "A"},
    {"email": "b@b.com", "name": "B"},
]


def compiled(statement, dialect):
    return str(statement.compile(dialect=dialect))


class TestBuildUpsertStatement(TestCase):
    def test_postgres_uses_on_conflict_do_update(self):
        statement = build_upsert_statement("postgres", "users", ROWS, ["email"], ["name"])
        sql = compiled(statement, postgresql.dialect())
        self.assertIn("ON CONFLICT (email) DO UPDATE SET name = excluded.name", sql)

    def test_sqlite_uses_on_conflict_do_update(self):
        statement = build_upsert_statement("sqlite", "users", ROWS, ["email"], ["name"])
        sql = compiled(statement, sqlite.dialect())
        self.assertIn("ON CONFLICT (email) DO UPDATE SET name = excluded.name", sql)

    def test_mysql_uses_on_duplicate_key_update(self):
        statement = build_upsert_statement("mysql", "users", ROWS, ["email"], ["name"])
        sql = compiled(statement, mysql.dialect())
        self.assertIn("ON DUPLICATE KEY UPDATE name = VALUES(name)", sql)

    def test_bulk_values_are_a_single_statement(self):
        statement = build_upsert_statement("postgres", "users", ROWS, ["email"], ["name"])
        sql = compiled(statement, postgresql.dialect())
        # Two value tuples → one multi-row INSERT, not a loop.
        self.assertEqual(sql.count("INSERT INTO"), 1)
        self.assertIn("VALUES", sql)

    def test_empty_update_list_falls_back_to_do_nothing(self):
        statement = build_upsert_statement("postgres", "users", ROWS, ["email"], [])
        sql = compiled(statement, postgresql.dialect())
        self.assertIn("ON CONFLICT (email) DO NOTHING", sql)

    def test_unsupported_driver_raises(self):
        with self.assertRaises(ValueError):
            build_upsert_statement("oracle", "users", ROWS, ["email"], ["name"])

import unittest

from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar


class TestPostgresInsertGrammar(unittest.TestCase):
    """Grammar-level unit tests — no live Postgres connection required."""

    def test_insert_format_is_defined(self):
        result = PostgresGrammar().insert_format()
        self.assertEqual(result, "INSERT INTO {table} ({columns}) VALUES ({values})")

    def test_bulk_insert_format_is_defined(self):
        result = PostgresGrammar().bulk_insert_format()
        self.assertEqual(result, "INSERT INTO {table} ({columns}) VALUES {values}")

    def test_compile_bulk_create_builds_multi_row_insert(self):
        # Regression: PostgresGrammar previously lacked bulk_insert_format(),
        # so compiling a bulk create raised AttributeError.
        rows = [
            {"name": "Joe", "email": "joe@example.com"},
            {"name": "Bob", "email": "bob@example.com"},
        ]
        grammar = PostgresGrammar(columns=rows, table="users")

        sql = grammar.compile("bulk_create")._sql

        self.assertEqual(
            sql,
            'INSERT INTO "users" ("name", "email") VALUES '
            "('Joe', 'joe@example.com'), ('Bob', 'bob@example.com')",
        )


if __name__ == "__main__":
    unittest.main()

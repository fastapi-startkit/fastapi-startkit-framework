import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar

GRAMMARS = {
    "sqlite": SQLiteGrammar,
    "mysql": MySQLGrammar,
    "postgres": PostgresGrammar,
    "mssql": MSSQLGrammar,
}

# Table name is quoted per dialect; the compared columns stay bare identifiers.
TABLE = {"sqlite": '"users"', "mysql": "`users`", "postgres": '"users"', "mssql": "[users]"}
ACTIVE = {
    "sqlite": '"users"."active"',
    "mysql": "`users`.`active`",
    "postgres": '"users"."active"',
    "mssql": "[users].[active]",
}


def qb(grammar):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = "users"
    return q


class TestWhereColumnGrammar(unittest.TestCase):
    """Grammar-level SQL parity for where_column / or_where_column across all dialects."""

    def test_where_column_two_arg_equality(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar).where_column("first_name", "last_name").to_sql()
                self.assertEqual(sql, f"SELECT * FROM {TABLE[name]} WHERE first_name = last_name")

    def test_where_column_three_arg_operator(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar).where_column("updated_at", ">", "created_at").to_sql()
                self.assertEqual(sql, f"SELECT * FROM {TABLE[name]} WHERE updated_at > created_at")

    def test_where_column_all_operators(self):
        for name, grammar in GRAMMARS.items():
            for op in ("=", "!=", "<>", ">", ">=", "<", "<="):
                with self.subTest(grammar=name, operator=op):
                    sql = qb(grammar).where_column("a", op, "b").to_sql()
                    self.assertEqual(sql, f"SELECT * FROM {TABLE[name]} WHERE a {op} b")

    def test_where_column_rejects_invalid_operator(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                with self.assertRaises(ValueError):
                    qb(grammar).where_column("a", "BAD", "b")

    def test_or_where_column_two_arg_equality(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar).where("active", 1).or_where_column("first_name", "last_name").to_sql()
                self.assertEqual(
                    sql,
                    f"SELECT * FROM {TABLE[name]} WHERE {ACTIVE[name]} = '1' OR first_name = last_name",
                )

    def test_or_where_column_three_arg_operator(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = qb(grammar).where("active", 1).or_where_column("updated_at", ">", "created_at").to_sql()
                self.assertEqual(
                    sql,
                    f"SELECT * FROM {TABLE[name]} WHERE {ACTIVE[name]} = '1' OR updated_at > created_at",
                )

    def test_or_where_column_uses_or_and_keeps_columns_as_identifiers(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                q = qb(grammar).where("active", 1).or_where_column("updated_at", ">", "created_at")
                sql = q.to_qmark()
                # OR join, correlated identifiers preserved, and only the literal value is bound.
                self.assertIn("OR updated_at > created_at", sql)
                self.assertEqual(list(q.get_bindings()), [1])

    def test_or_where_column_rejects_invalid_operator(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                with self.assertRaises(ValueError):
                    qb(grammar).or_where_column("a", "BAD", "b")


if __name__ == "__main__":
    unittest.main()

import datetime
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
    "mssql": MSSQLGrammar,
}

NULL_METHODS = ("where_null", "where_not_null", "or_where_null", "or_where_not_null")

SINCE = datetime.date(2026, 1, 1)


def qb(grammar, table="users"):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = table
    return q


class TestNullWhereBindingsGrammar(unittest.TestCase):
    def assert_bindings(self, query, expected):
        sql = query.to_qmark()
        bindings = list(query.get_bindings())
        self.assertEqual(sql.count("?"), len(bindings), sql)
        self.assertEqual(bindings, expected)
        return sql

    def test_null_clauses_followed_by_where_bind_only_the_value(self):
        for method in NULL_METHODS:
            for name, grammar in GRAMMARS.items():
                with self.subTest(method=method, grammar=name):
                    query = getattr(qb(grammar), method)("deleted_at").where("created_at", ">=", SINCE)
                    sql = self.assert_bindings(query, [SINCE])
                    self.assertIn("IS NOT NULL" if "not" in method else "IS NULL", sql)

    def test_null_clauses_between_bound_values_keep_order(self):
        for method in NULL_METHODS:
            for name, grammar in GRAMMARS.items():
                with self.subTest(method=method, grammar=name):
                    query = getattr(qb(grammar).where("name", "Joe"), method)("deleted_at")
                    query.where("created_at", ">=", SINCE).where_in("id", [1, 2]).or_where("age", "<", 30)
                    self.assert_bindings(query, ["Joe", SINCE, 1, 2, 30])

    def test_chained_null_clauses_bind_nothing(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = qb(grammar).where_not_null("a").where_null("b").or_where_not_null("c").or_where_null("d")
                self.assert_bindings(query, [])

    def test_no_value_clauses_mixed_with_null_clauses(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = (
                    qb(grammar)
                    .where_not_null("deleted_at")
                    .where_column("updated_at", ">", "created_at")
                    .where_raw("1 = 1")
                    .where("created_at", ">=", SINCE)
                    .where_raw("age > ?", (18,))
                )
                self.assert_bindings(query, [SINCE, 18])

    def test_exists_subquery_with_null_clause(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                inner = qb(grammar, "posts").where_not_null("published_at").where("votes", ">", 5)
                query = qb(grammar).where_exists(inner).where("created_at", ">=", SINCE)
                self.assert_bindings(query, [5, SINCE])


if __name__ == "__main__":
    unittest.main()

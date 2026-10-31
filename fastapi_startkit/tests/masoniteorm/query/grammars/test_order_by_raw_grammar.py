import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar

GRAMMARS = [SQLiteGrammar, MySQLGrammar, PostgresGrammar, MSSQLGrammar]


def qb(grammar):
    query = QueryBuilder(connection=None, grammar=grammar, processor=None)
    query._table = "posts"
    return query


class TestOrderByRawGrammar(unittest.TestCase):
    def test_consecutive_raw_orders_are_separated(self):
        for grammar in GRAMMARS:
            with self.subTest(grammar=grammar.__name__):
                sql = qb(grammar).order_by_raw("posts.rank DESC").order_by_raw("posts.title, posts.id").to_qmark()
                self.assertTrue(sql.endswith("ORDER BY posts.rank DESC, posts.title, posts.id"), sql)

    def test_a_raw_order_after_a_column_order_is_separated(self):
        for grammar in GRAMMARS:
            with self.subTest(grammar=grammar.__name__):
                sql = qb(grammar).order_by("rank", "desc").order_by_raw("posts.id").to_qmark()
                self.assertTrue(sql.endswith("DESC, posts.id"), sql)

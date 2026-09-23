import unittest

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

QUOTE = {
    "sqlite": '"{}"',
    "mysql": "`{}`",
    "postgres": '"{}"',
    "mssql": "[{}]",
}


def q(name, identifier):
    return QUOTE[name].format(identifier)


class TestTableColumnStringGrammar(unittest.TestCase):
    """Column compilation in _table_column_string across all dialects."""

    def test_plain_column_has_no_alias(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = grammar(table="users")._table_column_string("name")
                self.assertEqual(sql, f"{q(name, 'users')}.{q(name, 'name')}")

    def test_alias_is_prefixed_with_a_space(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                sql = grammar(table="users")._table_column_string("name", alias="n", separator=", ")
                self.assertEqual(sql, f"{q(name, 'users')}.{q(name, 'name')} AS n, ")

    def test_star_uses_select_all_format(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                g = grammar(table="users")
                self.assertEqual(g._table_column_string("*"), f"{q(name, 'users')}.*")
                self.assertEqual(g._table_column_string("posts.*"), f"{q(name, 'posts')}.*")

    def test_format_follows_current_action(self):
        g = PostgresGrammar(table="users")
        g._action = "update"
        self.assertEqual(g._table_column_string("name"), '"name"')

    def test_unknown_action_raises(self):
        g = SQLiteGrammar(table="users")
        g._action = "bogus"
        with self.assertRaises(KeyError):
            g._table_column_string("name")

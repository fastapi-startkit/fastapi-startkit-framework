import unittest
from unittest.mock import AsyncMock

from ..test_case import TestCase
from ..fixtures.db import DB
from ...fixtures.model import User


class TestQueryBuilderRelationshipsSQL(unittest.TestCase):
    """SQL generation tests — no DB required, just to_sql() assertions."""

    def test_where_has_generates_exists_subquery(self):
        sql = User.query().where_has("articles").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS (SELECT * FROM "articles" WHERE articles.user_id = users.id)',
        )

    def test_where_has_with_callback_appends_condition(self):
        sql = User.query().where_has("articles", lambda q: q.where("id", 1)).to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS '
            '(SELECT * FROM "articles" WHERE articles.user_id = users.id AND "articles"."id" = \'1\')',
        )

    def test_where_has_profile_uses_correct_table(self):
        sql = User.query().where_has("profile").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS (SELECT * FROM "profiles" WHERE profiles.user_id = users.id)',
        )


class TestQueryBuilderRelationshipsExecution(TestCase):
    """Execution tests — intercept the connection to assert exact SQL + bindings."""

    async def test_where_has_executes_exists_subquery(self):
        mock_select = AsyncMock(return_value=[])
        DB.connection("sqlite").select = mock_select

        await User.where_has("articles").get()

        mock_select.assert_called_once()
        sql, bindings = mock_select.call_args[0]
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS (SELECT * FROM "articles" WHERE articles.user_id = users.id)',
        )
        self.assertEqual(list(bindings), [])

    async def test_where_has_with_callback_passes_correct_sql_and_bindings(self):
        mock_select = AsyncMock(return_value=[])
        DB.connection("sqlite").select = mock_select

        await User.where_has("articles", lambda q: q.where("id", 1)).get()

        mock_select.assert_called_once()
        sql, bindings = mock_select.call_args[0]
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS '
            '(SELECT * FROM "articles" WHERE articles.user_id = users.id AND "articles"."id" = ?)',
        )
        self.assertEqual(list(bindings), [1])

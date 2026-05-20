
from ...fixtures.model import User
from ..fixtures.db import DB
from ..test_case import TestCase


class TestQueryBuilderEagerLoading(TestCase):
    async def test_with_profile_get_executes_two_selects(self):
        calls = []
        real_select = DB.connection("sqlite").select

        async def capturing_select(sql, bindings=()):
            calls.append((sql, list(bindings)))
            return await real_select(sql, bindings)

        DB.connection("sqlite").select = capturing_select
        await User.with_("profile").get()

        self.assertEqual(len(calls), 2)
        users_sql, users_bindings = calls[0]
        self.assertEqual(users_sql, 'SELECT * FROM "users"')
        self.assertEqual(users_bindings, [])

        profiles_sql, profiles_bindings = calls[1]
        self.assertEqual(
            profiles_sql,
            'SELECT * FROM "profiles" WHERE "profiles"."user_id" IN (?, ?)',
        )
        self.assertEqual(profiles_bindings, [1, 2])

    async def test_with_profile_where_first_executes_two_selects(self):
        calls = []
        real_select = DB.connection("sqlite").select

        async def capturing_select(sql, bindings=()):
            calls.append((sql, list(bindings)))
            return await real_select(sql, bindings)

        DB.connection("sqlite").select = capturing_select
        await User.with_("profile").where("id", 1).first()

        self.assertEqual(len(calls), 2)
        users_sql, users_bindings = calls[0]
        self.assertEqual(
            users_sql,
            'SELECT * FROM "users" WHERE "users"."id" = ? LIMIT 1',
        )
        self.assertEqual(users_bindings, [1])

        profiles_sql, profiles_bindings = calls[1]
        self.assertEqual(
            profiles_sql,
            'SELECT * FROM "profiles" WHERE "profiles"."user_id" IN (?)',
        )
        self.assertEqual(profiles_bindings, [1])

    async def test_with_articles_get_executes_two_selects(self):
        calls = []
        real_select = DB.connection("sqlite").select

        async def capturing_select(sql, bindings=()):
            calls.append((sql, list(bindings)))
            return await real_select(sql, bindings)

        DB.connection("sqlite").select = capturing_select
        await User.with_("articles").get()

        self.assertEqual(len(calls), 2)
        users_sql, users_bindings = calls[0]
        self.assertEqual(users_sql, 'SELECT * FROM "users"')
        self.assertEqual(users_bindings, [])

        articles_sql, articles_bindings = calls[1]
        self.assertEqual(
            articles_sql,
            'SELECT * FROM "articles" WHERE "articles"."user_id" IN (?, ?)',
        )
        self.assertEqual(articles_bindings, [1, 2])

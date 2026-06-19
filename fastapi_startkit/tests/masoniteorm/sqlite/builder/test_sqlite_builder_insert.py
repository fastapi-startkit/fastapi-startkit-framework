from unittest.mock import AsyncMock

from ..fixtures.db import DB
from ...fixtures.model import User
from ..test_case import TestCase


class TestQueryBuilderInsert(TestCase):
    async def test_insert_creates_record_and_returns_model(self):
        user = await User.create({"email": "insert@test.com", "name": "Insert User", "is_admin": False})
        assert isinstance(user.id, int)
        assert user.name == "Insert User"

    async def test_insert_via_builder(self):
        await User.query().insert({"email": "bulk@test.com", "name": "Bulk User", "is_admin": False})
        user = await User.where("email", "bulk@test.com").first()
        assert user is not None
        assert user.name == "Bulk User"

    async def test_bulk_insert_sql_single(self):
        mock_insert = AsyncMock(return_value=1)
        DB.connection("sqlite").insert = mock_insert

        await User.query().insert({"name": "Joe"})

        mock_insert.assert_called_once()
        sql, bindings = mock_insert.call_args[0]
        self.assertEqual(sql, 'INSERT INTO "users" ("name") VALUES (?)')
        self.assertEqual(list(bindings), ["Joe"])

    async def test_bulk_insert_sql_multiple(self):
        mock_insert = AsyncMock(return_value=3)
        DB.connection("sqlite").insert = mock_insert

        await User.query().insert([{"name": "Joe"}, {"name": "Bill"}, {"name": "John"}])

        mock_insert.assert_called_once()
        sql, bindings = mock_insert.call_args[0]
        self.assertEqual(sql, 'INSERT INTO "users" ("name") VALUES (?), (?), (?)')
        self.assertEqual(list(bindings), ["Joe", "Bill", "John"])

    async def test_insert_classmethod_single_row(self):
        await User.insert({"email": "classmethod@test.com", "name": "CM User", "is_admin": False})
        user = await User.where("email", "classmethod@test.com").first()
        assert user is not None
        assert user.name == "CM User"

    async def test_insert_classmethod_bulk_rows(self):
        mock_insert = AsyncMock(return_value=2)
        DB.connection("sqlite").insert = mock_insert
        await User.insert([{"name": "Alice"}, {"name": "Bob"}])
        mock_insert.assert_called_once()
        sql, bindings = mock_insert.call_args[0]
        self.assertIn('INSERT INTO', sql)

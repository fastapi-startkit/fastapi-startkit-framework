import unittest
from unittest.mock import AsyncMock

from ..fixtures.db import DB
from ...fixtures.model import User
from ..test_case import TestCase
from fastapi_startkit.masoniteorm import ModelNotFoundException


class SqliteTestQueryBuilderModel(TestCase):
    async def test_update_specific_record(self):
        mock_update = AsyncMock(return_value=1)
        DB.connection("default").update = mock_update

        user = await User.first()
        await user.update({"name": "joe"})

        mock_update.assert_called_once()
        sql, bindings = mock_update.call_args[0]

        self.assertEqual(sql, 'UPDATE "users" SET "name" = ? WHERE "id" = ?')
        self.assertEqual(bindings, ["joe", 1])

    async def test_update_all_records(self):
        mock_update = AsyncMock(return_value=1)
        DB.connection("default").update = mock_update

        await User.query().update({"name": "joe"})

        mock_update.assert_called_once()
        sql, bindings = mock_update.call_args[0]

        self.assertEqual(sql, 'UPDATE "users" SET "name" = ?')
        self.assertEqual(bindings, ["joe"])

    async def test_can_find_list(self):
        mock_select = AsyncMock(return_value=[])
        DB.connection("default").select = mock_select

        await User.find(1)

        mock_select.assert_called_once()
        sql, bindings = mock_select.call_args[0]
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."id" = ? LIMIT 1')
        self.assertIn(1, bindings)

    async def test_find_or_fail_returns_model_when_found(self):
        user = await User.find_or_fail(1)
        self.assertIsInstance(user, User)
        self.assertEqual(user.id, 1)

    async def test_find_or_fail_raises_when_not_found(self):
        with self.assertRaises(ModelNotFoundException):
            await User.find_or_fail(99999)

    async def test_find_or_fail_exception_has_404_status(self):
        try:
            await User.find_or_fail(99999)
        except ModelNotFoundException as e:
            self.assertEqual(e.get_status(), 404)

    async def test_find_or_fail_exception_message_contains_key(self):
        try:
            await User.find_or_fail(99999)
        except ModelNotFoundException as e:
            self.assertIn("99999", str(e))

    async def test_can_set_and_retrieve_attribute(self):
        user = await User.first()
        user.name = "updated"
        self.assertEqual(user.name, "updated")

    async def test_update_only_changed_attributes(self):
        mock_update = AsyncMock(return_value=1)
        DB.connection("default").update = mock_update

        user = await User.first()
        await user.update({"name": "new_name", "email": user.email})

        mock_update.assert_called_once()
        sql, bindings = mock_update.call_args[0]

        self.assertEqual(sql, 'UPDATE "users" SET "name" = ? WHERE "id" = ?')
        self.assertEqual(bindings, ["new_name", 1])

    @unittest.skip("__selects__ not yet implemented")
    async def test_model_can_use_selects(self):
        pass

    @unittest.skip("all() not yet implemented")
    async def test_model_can_use_selects_from_methods(self):
        pass

    @unittest.skip("between() not yet implemented")
    async def test_should_collect_correct_amount_data_using_between(self):
        pass

    @unittest.skip("not_between() not yet implemented")
    async def test_should_collect_correct_amount_data_using_not_between(self):
        pass

    @unittest.skip("get_columns() not yet implemented")
    async def test_get_columns(self):
        pass

    @unittest.skip("__hidden__ not yet implemented")
    async def test_should_return_relation_applying_hidden_attributes(self):
        pass

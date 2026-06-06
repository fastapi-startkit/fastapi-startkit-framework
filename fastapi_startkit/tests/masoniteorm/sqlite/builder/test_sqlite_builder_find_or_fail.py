from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException

from ...fixtures.model import User
from ..test_case import TestCase


class TestFindOrFail(TestCase):
    async def test_find_or_fail_returns_record_when_found(self):
        # The seeder inserts a user with id=1; it should be returned cleanly.
        user = await User.find_or_fail(1)
        self.assertIsNotNone(user)

    async def test_find_or_fail_raises_for_missing_key(self):
        with self.assertRaises(ModelNotFoundException):
            await User.find_or_fail(999999)

    async def test_find_or_fail_exception_message_contains_model_name(self):
        """Exception message must say 'User', not the generic 'type' or 'None'."""
        try:
            await User.find_or_fail(999999)
            self.fail("ModelNotFoundException was not raised")
        except ModelNotFoundException as exc:
            msg = str(exc)
            self.assertIn("User", msg)
            self.assertNotIn("type", msg)
            self.assertNotIn("None", msg)

    async def test_first_or_fail_exception_message_contains_model_name(self):
        """first_or_fail must also use the real model name, not 'type' or 'None'."""
        try:
            await User.where("email", "no-such-user@example.com").first_or_fail()
            self.fail("ModelNotFoundException was not raised")
        except ModelNotFoundException as exc:
            msg = str(exc)
            self.assertIn("User", msg)
            self.assertNotIn("type", msg)
            self.assertNotIn("None", msg)

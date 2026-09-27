"""
Tests for the Laravel-style instance-level ``Model.touch()`` method.

Scope is deliberately narrow: bump ``updated_at`` on a single persisted
instance and leave everything else alone. No relationship cascading and no
bulk query-builder touch — those are separate, out-of-scope features.
"""

from tests.masoniteorm.fixtures.model import Profile, User
from tests.masoniteorm.sqlite.test_case import TestCase


class TestTouch(TestCase):
    async def test_touch_returns_true_on_success(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})

        self.assertTrue(await user.touch())

    async def test_touch_sets_updated_at_on_instance(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})
        self.assertIsNone(user.updated_at)

        await user.touch()

        self.assertIsNotNone(user.updated_at)

    async def test_touch_persists_updated_at_to_the_database(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})

        await user.touch()

        fetched = await User.find(user.id)
        self.assertEqual(fetched.updated_at, user.updated_at)

    async def test_touch_advances_an_already_set_updated_at(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})
        await user.touch()
        first_touch = user.updated_at

        await user.touch()

        self.assertGreaterEqual(user.updated_at, first_touch)

    async def test_touch_does_not_persist_other_dirty_attributes(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})
        user.name = "Changed"

        await user.touch()

        fetched = await User.find(user.id)
        self.assertEqual(fetched.name, "Alex")

    async def test_touch_leaves_other_dirty_attributes_dirty_on_the_instance(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})
        user.name = "Changed"

        await user.touch()

        self.assertTrue(user.is_dirty())
        self.assertIn("name", user.get_dirty())

    async def test_touch_does_not_mark_updated_at_as_dirty(self):
        user = await User.create({"name": "Alex", "email": "alex@gmail.com"})

        await user.touch()

        self.assertNotIn("updated_at", user.get_dirty())

    async def test_touch_is_noop_when_timestamps_disabled(self):
        profile = await Profile.create({"name": "P1", "user_id": 1})

        result = await profile.touch()

        self.assertFalse(result)

    async def test_touch_is_noop_on_an_unsaved_model(self):
        user = User(name="Alex", email="alex@gmail.com")

        result = await user.touch()

        self.assertFalse(result)
        self.assertIsNone(user.updated_at)

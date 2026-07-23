"""
Tests for fastapi_startkit.masoniteorm.factory.factory.Factory

All tests run against an in-memory SQLite database via the shared TestCase
base class (RefreshDatabase + IsolatedAsyncioTestCase), which migrates and
wipes the schema around every test.
"""

from faker import Faker

from fastapi_startkit.masoniteorm import Factory

from ..fixtures.model import Articles, Profile, User
from .test_case import TestCase

# ---------------------------------------------------------------------------
# Concrete factory definitions used throughout these tests
# ---------------------------------------------------------------------------

UNIQUE_EMAIL_COUNTER = [0]  # simple counter for unique e-mails in tests


def _unique_email(prefix: str = "user") -> str:
    UNIQUE_EMAIL_COUNTER[0] += 1
    return f"{prefix}{UNIQUE_EMAIL_COUNTER[0]}@example.com"


class UserFactory(Factory):
    model = User

    def definition(self) -> dict:
        return {
            "name": self.fake.name(),
            "email": _unique_email(),
            "is_admin": False,
        }

    def admin(self) -> "UserFactory":
        """State: the user is an admin."""
        return self.state(lambda attrs: {"is_admin": True})


class ProfileFactory(Factory):
    """Profile belongs to User (user_id FK)."""

    model = Profile

    def definition(self) -> dict:
        return {"name": self.fake.name()}


class ArticleFactory(Factory):
    """Article belongs to User (user_id FK)."""

    model = Articles

    def definition(self) -> dict:
        return {
            "title": self.fake.sentence(nb_words=4),
            "published_date": "2024-01-01 00:00:00",
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFactoryFakeAttribute(TestCase):
    """self.fake must be a Faker instance."""

    async def test_fake_is_faker_instance(self):
        factory = UserFactory.new()
        self.assertIsInstance(factory.fake, Faker)

    async def test_fake_can_generate_values(self):
        factory = UserFactory.new()
        name = factory.fake.name()
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0)


class TestFactoryMake(TestCase):
    """make() builds in-memory instances without persisting."""

    async def test_make_returns_model_instance(self):
        user = await UserFactory.new().make()
        self.assertIsInstance(user, User)

    async def test_make_does_not_persist(self):
        user = await UserFactory.new().make()
        # A freshly made instance has no PK assigned by the database
        self.assertFalse(user.is_loaded())

    async def test_make_with_overrides(self):
        user = await UserFactory.new().make(name="Custom Name", is_admin=True)
        self.assertEqual(user.get_attribute("name"), "Custom Name")
        self.assertEqual(user.get_attribute("is_admin"), True)

    async def test_make_without_overrides_uses_definition(self):
        user = await UserFactory.new().make()
        # name comes from self.fake.name() — just verify it's a non-empty string
        name = user.get_attribute("name")
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0)


class TestFactoryCreate(TestCase):
    """create() persists to the DB and returns a hydrated model."""

    async def test_create_returns_model_instance(self):
        user = await UserFactory.new().create()
        self.assertIsInstance(user, User)

    async def test_create_assigns_primary_key(self):
        user = await UserFactory.new().create()
        self.assertIsNotNone(user.get_attribute("id"))

    async def test_created_record_exists_in_db(self):
        user = await UserFactory.new().create()
        found = await User.find(user.get_attribute("id"))
        self.assertIsNotNone(found)
        self.assertEqual(found.get_attribute("id"), user.get_attribute("id"))

    async def test_create_with_overrides(self):
        email = _unique_email("override")
        user = await UserFactory.new().create(email=email, is_admin=True)
        self.assertEqual(user.get_attribute("email"), email)
        self.assertEqual(user.get_attribute("is_admin"), True)

    async def test_create_persists_overridden_fields(self):
        email = _unique_email("persist")
        await UserFactory.new().create(email=email)
        found = await User.where("email", email).first()
        self.assertIsNotNone(found)


class TestFactoryCount(TestCase):
    """count(n) produces lists from both make() and create()."""

    async def test_count_make_returns_list(self):
        users = await UserFactory.new().count(3).make()
        self.assertIsInstance(users, list)
        self.assertEqual(len(users), 3)

    async def test_count_make_all_are_model_instances(self):
        users = await UserFactory.new().count(3).make()
        for u in users:
            self.assertIsInstance(u, User)

    async def test_count_create_returns_list(self):
        users = await UserFactory.new().count(3).create()
        self.assertIsInstance(users, list)
        self.assertEqual(len(users), 3)

    async def test_count_create_all_have_pk(self):
        users = await UserFactory.new().count(3).create()
        for u in users:
            self.assertIsNotNone(u.get_attribute("id"))

    async def test_count_create_persists_all_records(self):
        users = await UserFactory.new().count(4).create()
        ids = [u.get_attribute("id") for u in users]
        # All IDs must be unique
        self.assertEqual(len(ids), len(set(ids)))

    async def test_count_one_still_returns_single(self):
        user = await UserFactory.new().count(1).make()
        # count(1) still returns single instance (not a list)
        self.assertIsInstance(user, User)

    async def test_count_one_create_still_returns_single(self):
        user = await UserFactory.new().count(1).create()
        self.assertIsInstance(user, User)


class TestFactoryState(TestCase):
    """state() merges partial overrides on top of definition()."""

    async def test_state_via_lambda(self):
        user = await UserFactory.new().state(lambda attrs: {"is_admin": True}).create()
        self.assertEqual(user.get_attribute("is_admin"), True)

    async def test_named_state_method(self):
        user = await UserFactory.new().admin().create()
        self.assertEqual(user.get_attribute("is_admin"), True)

    async def test_state_does_not_affect_other_fields(self):
        user = await UserFactory.new().admin().create()
        name = user.get_attribute("name")
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0)

    async def test_multiple_states_are_merged(self):
        user = await (
            UserFactory.new()
            .state(lambda attrs: {"is_admin": True})
            .state(lambda attrs: {"name": "Multi State"})
            .create()
        )
        self.assertEqual(user.get_attribute("is_admin"), True)
        self.assertEqual(user.get_attribute("name"), "Multi State")

    async def test_override_takes_precedence_over_state(self):
        user = await UserFactory.new().admin().create(is_admin=False)
        self.assertEqual(user.get_attribute("is_admin"), False)


class TestFactoryLifecycleHooks(TestCase):
    """after_making() and after_creating() callbacks are invoked."""

    async def test_after_making_sync_callback_called(self):
        called_with = []

        def cb(instance):
            called_with.append(instance)

        user = await UserFactory.new().after_making(cb).make()
        self.assertEqual(len(called_with), 1)
        self.assertIs(called_with[0], user)

    async def test_after_making_async_callback_called(self):
        called_with = []

        async def cb(instance):
            called_with.append(instance)

        user = await UserFactory.new().after_making(cb).make()
        self.assertEqual(len(called_with), 1)
        self.assertIs(called_with[0], user)

    async def test_after_creating_sync_callback_called(self):
        called_with = []

        def cb(instance):
            called_with.append(instance)

        user = await UserFactory.new().after_creating(cb).create()
        self.assertEqual(len(called_with), 1)
        self.assertIs(called_with[0], user)

    async def test_after_creating_async_callback_called(self):
        called_with = []

        async def cb(instance):
            called_with.append(instance)

        user = await UserFactory.new().after_creating(cb).create()
        self.assertEqual(len(called_with), 1)
        self.assertIs(called_with[0], user)

    async def test_after_making_not_called_on_create(self):
        making_calls = []
        creating_calls = []

        await (
            UserFactory.new()
            .after_making(lambda i: making_calls.append(i))
            .after_creating(lambda i: creating_calls.append(i))
            .create()
        )
        # after_making should NOT fire during create()
        self.assertEqual(len(making_calls), 0)
        self.assertEqual(len(creating_calls), 1)

    async def test_after_making_called_for_each_in_count(self):
        calls = []

        await UserFactory.new().count(3).after_making(lambda i: calls.append(i)).make()
        self.assertEqual(len(calls), 3)

    async def test_after_creating_called_for_each_in_count(self):
        calls = []

        await UserFactory.new().count(3).after_creating(lambda i: calls.append(i)).create()
        self.assertEqual(len(calls), 3)


class TestFactoryConfigure(TestCase):
    """configure() is called automatically by new() when overridden."""

    async def test_configure_registers_after_creating_hook(self):
        calls = []

        class HookedUserFactory(Factory):
            model = User

            def definition(self) -> dict:
                return {"name": "Hook Test", "email": _unique_email("hook")}

            def configure(self):
                return self.after_creating(lambda i: calls.append(i))

        user = await HookedUserFactory.new().create()
        self.assertIsInstance(user, User)
        self.assertEqual(len(calls), 1)

    async def test_configure_not_called_when_not_overridden(self):
        # UserFactory does not override configure(); new() must not crash
        factory = UserFactory.new()
        self.assertIsNotNone(factory)


class TestFactoryHasRelationship(TestCase):
    """has() creates child records with the parent FK injected."""

    async def test_has_creates_child_with_fk(self):
        # User has many Articles; article.user_id = user.id
        user = await UserFactory.new().has(ArticleFactory.new()).create()
        user_id = user.get_attribute("id")
        article = await Articles.where("user_id", user_id).first()
        self.assertIsNotNone(article)
        self.assertEqual(article.get_attribute("user_id"), user_id)

    async def test_has_with_count_creates_multiple_children(self):
        user = await UserFactory.new().has(ArticleFactory.new().count(3)).create()
        user_id = user.get_attribute("id")
        articles = await Articles.where("user_id", user_id).get()
        self.assertEqual(len(articles), 3)


class TestFactoryForRelationship(TestCase):
    """for_() creates parent record and injects its PK as FK."""

    async def test_for_creates_parent_and_injects_fk(self):
        # Profile has user_id FK; for_(UserFactory) should create a User first
        profile = await ProfileFactory.new().for_(UserFactory.new()).create()
        user_id = profile.get_attribute("user_id")
        self.assertIsNotNone(user_id)
        user = await User.find(user_id)
        self.assertIsNotNone(user)

    async def test_for_with_count_injects_same_parent(self):
        # All profiles share the same parent User
        profiles = await ProfileFactory.new().count(2).for_(UserFactory.new()).create()
        user_ids = {p.get_attribute("user_id") for p in profiles}
        # Both profiles must reference the SAME user (for_ creates parent once)
        self.assertEqual(len(user_ids), 1)


class TestFactoryNew(TestCase):
    """new() returns a fresh factory instance each call."""

    async def test_new_returns_factory_instance(self):
        factory = UserFactory.new()
        self.assertIsInstance(factory, UserFactory)

    async def test_new_instances_are_independent(self):
        f1 = UserFactory.new().count(2)
        f2 = UserFactory.new()
        # f2 should still have count=1 (default), unaffected by f1
        self.assertEqual(f2._count, 1)
        self.assertEqual(f1._count, 2)

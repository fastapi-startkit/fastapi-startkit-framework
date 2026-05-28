from fastapi_startkit.masoniteorm.models.model import Model
from tests.masoniteorm.fixtures.model import User
from tests.masoniteorm.sqlite.test_case import TestCase


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema(TestCase):
    async def test_create_table(self):
        assert await self.schema.on("default").has_table("users")

    async def test_drop_table_if_exists(self):
        await self.schema.drop_table_if_exists("nonexistent_table")

    async def test_drop_table_removes_table(self):
        await self.schema.drop_table("users")
        assert not await self.schema.on("default").has_table("users")


# ---------------------------------------------------------------------------
# INSERT (Model.save on a new record)
# ---------------------------------------------------------------------------


class TestModelInsert(TestCase):
    async def test_save_inserts_row(self):
        user = User(name="Alex", email="alex@gmail.com")
        assert await user.save() is True

    async def test_save_sets_exists_flag(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user._exists is True

    async def test_save_sets_was_recently_created(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user._was_recently_created is True

    async def test_save_populates_primary_key(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user.id is not None
        assert isinstance(user.id, int)


# ---------------------------------------------------------------------------
# UPDATE (Model.save on an existing record)
# ---------------------------------------------------------------------------


class TestModelUpdate(TestCase):
    async def test_save_updates_dirty_attribute(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        user.name = "Ram"
        assert await user.save() is True
        assert user.name == "Ram"

    async def test_save_update_clears_dirty(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        user.name = "Ram"
        await user.save()

        assert not user.is_dirty()

    async def test_save_noop_when_not_dirty(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()

        assert await user.save() is True

    async def test_save_update_keeps_same_id(self):
        user = User(name="Alex", email="alex@gmail.com")
        await user.save()
        original_id = user.id

        user.name = "Ram"
        await user.save()

        assert user.id == original_id

    async def test_update_iterating_all_persists_changes(self):
        await User.create({"name": "Alice", "email": "alice@test.com"})
        await User.create({"name": "Bob", "email": "bob@test.com"})

        for user in await User.all():
            await user.update({"name": "Updated"})

        assert all(u.name == "Updated" for u in await User.all())


# ---------------------------------------------------------------------------
# Fillable guard
# ---------------------------------------------------------------------------


class TestFillable(TestCase):
    async def test_annotated_fields_are_in_fillable(self):
        class Post(Model):
            __table__ = "posts"
            title: str
            body: str

        assert "title" in Post.__fillable__
        assert "body" in Post.__fillable__

    async def test_framework_fields_excluded_from_fillable(self):
        class Post(Model):
            __table__ = "posts"
            title: str

        assert "db_manager" not in Post.__fillable__
        assert "created_at" not in Post.__fillable__
        assert "updated_at" not in Post.__fillable__

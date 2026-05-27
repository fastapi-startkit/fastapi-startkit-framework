import pytest

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.masoniteorm.models.fields import DateTimeField
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.model import Model

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SQLITE_CONFIG = {
    "default": "sqlite",
    "connections": {
        "sqlite": {
            "driver": "sqlite",
            "url": "sqlite+aiosqlite:///:memory:",
        },
    },
}


@pytest.fixture
def db():
    return DatabaseManager(ConnectionFactory(), SQLITE_CONFIG)


@pytest.fixture
def UserModel(db):
    class User(Model):
        id: int
        name: str
        email: str
        email_verified_at: Carbon = DateTimeField(fmt="%Y-%m-%d %H:%M:%S", tz="UTC")

    User.db_manager = db
    return User


@pytest.fixture
async def users_table(db):
    """Create the user's table and drop it after each test."""
    schema = db.get_schema_builder()
    await schema.drop_table_if_exists("users")
    async with await schema.on("default").create("users") as table:
        table.id()
        table.string("name")
        table.string("email").unique()
        table.timestamp("email_verified_at").nullable()
        table.timestamps()
    yield schema
    await schema.drop_table_if_exists("users")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    async def test_create_table(self, db, users_table):
        schema = db.get_schema_builder()
        assert await schema.on("default").has_table("users")

    async def test_drop_table_if_exists(self, db):
        schema = db.get_schema_builder()
        # table does not exist yet — should not raise
        await schema.drop_table_if_exists("nonexistent_table")

    async def test_drop_table_removes_table(self, db, users_table):
        schema = db.get_schema_builder()
        await schema.drop_table("users")
        assert not await schema.on("default").has_table("users")


# ---------------------------------------------------------------------------
# INSERT (Model.save on a new record)
# ---------------------------------------------------------------------------


class TestModelInsert:
    async def test_save_inserts_row(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        saved = await user.save()

        assert saved is True

    async def test_save_sets_exists_flag(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user._exists is True

    async def test_save_sets_was_recently_created(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user._was_recently_created is True

    async def test_save_populates_primary_key(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        assert user.id is not None
        assert isinstance(user.id, int)

    async def test_save_with_datetime_field(self, UserModel, users_table):
        user = UserModel(
            name="Alex",
            email="alex@gmail.com",
            email_verified_at="2026-10-01 12:12:12",
        )
        saved = await user.save()

        assert saved is True
        assert user.email_verified_at.format("YYYY-MM-DD HH:mm:ss") == "2026-10-01 12:12:12"


# ---------------------------------------------------------------------------
# UPDATE (Model.save on an existing record)
# ---------------------------------------------------------------------------


class TestModelUpdate:
    async def test_save_updates_dirty_attribute(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        user.name = "Ram"
        saved = await user.save()

        assert saved is True
        assert user.name == "Ram"

    async def test_save_update_clears_dirty(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        user.name = "Ram"
        await user.save()

        assert not user.is_dirty()

    async def test_save_noop_when_not_dirty(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()

        # Nothing changed — save should return True without hitting the DB
        saved = await user.save()

        assert saved is True

    async def test_save_update_increments_id_stays_same(self, UserModel, users_table):
        user = UserModel(name="Alex", email="alex@gmail.com")
        await user.save()
        original_id = user.id

        user.name = "Ram"
        await user.save()

        assert user.id == original_id


# ---------------------------------------------------------------------------
# update() instance method — regression for GitHub issue #67
# ---------------------------------------------------------------------------


@pytest.fixture
def BareUserModel(db):
    """
    A model with no field annotations so __fillable__ = [].
    Used to verify that update() works even when attributes are not in __fillable__.
    """

    class BareUser(Model):
        __table__ = "users"

    BareUser.db_manager = db
    return BareUser


class TestModelUpdateMethod:
    async def test_records_from_all_have_exists_true(self, UserModel, users_table):
        """Records fetched via all() must have _exists=True so update() is not short-circuited."""
        await UserModel(name="Alex", email="alex@test.com").save()

        users = await UserModel.all()

        for user in users:
            assert user._exists is True

    async def test_update_persists_change_on_record_from_all(self, UserModel, users_table):
        """update() on a record fetched via all() must execute SQL and persist the change."""
        await UserModel(name="Alex", email="alex@test.com").save()

        users = await UserModel.all()
        user = users.first()
        await user.update({"name": "Updated"})

        refreshed = await UserModel.where("email", "alex@test.com").first()
        assert refreshed.name == "Updated"

    async def test_update_bypasses_fillable_guard(self, BareUserModel, users_table):
        """
        update() must update the attribute regardless of __fillable__.

        Previously, update() delegated to fill(), which silently ignores attributes
        not in __fillable__. For a model with no field annotations __fillable__ = [],
        so every attribute was silently skipped and no SQL was ever executed.

        Regression for: https://github.com/fastapi-startkit/fastapi-startkit-framework/issues/67
        """
        await BareUserModel.create({"name": "Initial", "email": "bare@test.com"})

        users = await BareUserModel.all()
        user = users.first()

        await user.update({"name": "Updated"})

        refreshed = await BareUserModel.where("email", "bare@test.com").first()
        assert refreshed.name == "Updated", (
            f"Expected 'Updated' but got '{refreshed.name}'. "
            "update() silently ignored the attribute because it was not in __fillable__."
        )

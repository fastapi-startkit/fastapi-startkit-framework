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

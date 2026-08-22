import pendulum
import pytest

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.exceptions.exceptions import DriverNotFound
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
async def db():
    manager = DatabaseManager(ConnectionFactory(), SQLITE_CONFIG)
    yield manager
    await manager.clear()


@pytest.fixture
def UserModel(db):
    class User(Model):
        id: int
        name: str
        email: str
        email_verified_at: Carbon = DateTimeField(fmt="%Y-%m-%d %H:%M:%S", tz="UTC")

    User.db_manager = db
    return User


# ---------------------------------------------------------------------------
# DatabaseManager / ConnectionFactory
# ---------------------------------------------------------------------------


class TestConnectionFactory:
    def test_build_url_uses_explicit_url(self):
        url = ConnectionFactory.build_url({"driver": "sqlite", "url": "sqlite+aiosqlite:///test.db"})
        assert url == "sqlite+aiosqlite:///test.db"

    def test_build_url_constructs_from_parts(self):
        url = ConnectionFactory.build_url(
            {
                "driver": "postgres",
                "username": "user",
                "password": "pass",
                "host": "localhost",
                "port": "5432",
                "database": "mydb",
            }
        )
        assert url == "postgresql+asyncpg://user:pass@localhost:5432/mydb"

    def test_make_returns_sqlite_connection(self):
        factory = ConnectionFactory()
        conn = factory.make(SQLITE_CONFIG["connections"]["sqlite"], "sqlite")
        from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection

        assert isinstance(conn, SQliteConnection)


class TestDatabaseManager:
    def test_resolves_default_connection_name(self, db):
        assert db.get_default_connection_name(None) == "sqlite"
        assert db.get_default_connection_name("default") == "sqlite"
        assert db.get_default_connection_name("sqlite") == "sqlite"

    def test_connection_is_cached(self, db):
        conn1 = db.connection("sqlite")
        conn2 = db.connection("sqlite")
        assert conn1 is conn2

    def test_connection_raises_for_missing_driver(self):
        # DatabaseManager now validates every configured connection's driver at
        # construction (app-boot) time, so an unsupported driver fails fast with
        # a friendly framework error before any engine is ever built, rather than
        # lazily on first use.
        factory = ConnectionFactory()
        bad_config = {
            "default": "mssql",
            "connections": {
                "mssql": {"driver": "mssql", "host": "localhost", "database": "db"},
            },
        }
        with pytest.raises(DriverNotFound, match="mssql"):
            DatabaseManager(factory, bad_config)


# ---------------------------------------------------------------------------
# Model attribute access
# ---------------------------------------------------------------------------


class TestModelAttributes:
    def test_name_attribute(self, UserModel):
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.name == "Alex"

    def test_email_attribute(self, UserModel):
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.email == "alex@gmail.com"

    def test_id_attribute_cast_to_int(self, UserModel):
        user = UserModel(id="42", name="Alex", email="alex@gmail.com")
        assert user.id == 42

    def test_missing_int_attribute_raises_type_error(self, UserModel):
        # IntCast.get() calls int(None) which raises TypeError — this is current
        # behavior for a declared-int field that was never assigned.
        user = UserModel(name="Alex", email="alex@gmail.com")
        with pytest.raises(TypeError):
            _ = user.id

    def test_unknown_attribute_returns_none(self, UserModel):
        # An attribute with no annotation or value returns None via get_attribute.
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.phone is None


# ---------------------------------------------------------------------------
# DateTimeField casting
# ---------------------------------------------------------------------------


class TestDateTimeField:
    def test_email_verified_at_is_pendulum_datetime(self, UserModel):
        user = UserModel(
            name="Alex",
            email="alex@gmail.com",
            email_verified_at="2026-10-01 12:12:12",
        )
        assert isinstance(user.email_verified_at, pendulum.DateTime)

    def test_email_verified_at_format(self, UserModel):
        user = UserModel(
            name="Alex",
            email="alex@gmail.com",
            email_verified_at="2026-10-01 12:12:12",
        )
        assert user.email_verified_at.format("YYYY-MM-DD HH:mm:ss") == "2026-10-01 12:12:12"

    def test_email_verified_at_none_when_not_set(self, UserModel):
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.email_verified_at is None


# ---------------------------------------------------------------------------
# created_at / updated_at (observer-driven timestamps)
# ---------------------------------------------------------------------------


class TestTimestampFields:
    def test_created_at_is_none_before_save(self, UserModel):
        """created_at is populated by the CreatedAtObserver on the 'creating' event,
        which fires during a save — not on plain instantiation."""
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.created_at is None

    def test_updated_at_is_none_before_save(self, UserModel):
        user = UserModel(name="Alex", email="alex@gmail.com")
        assert user.updated_at is None

    def test_observers_are_registered_on_model(self, UserModel):
        """CreatedAtField and UpdatedAtField register observers via __set_name__."""
        # At least one observer should be registered for the User class or its parents.
        all_observers = list(UserModel.__observers__.values())
        assert any(len(obs_list) > 0 for obs_list in all_observers)


# ---------------------------------------------------------------------------
# query() returns a QueryBuilder
# ---------------------------------------------------------------------------


class TestModelQuery:
    def test_query_returns_query_builder(self, UserModel):
        from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

        builder = UserModel.query()
        assert isinstance(builder, QueryBuilder)

    def test_query_builder_has_model_set(self, UserModel):

        builder = UserModel.query()
        assert builder._model is not None
        assert isinstance(builder._model, UserModel)

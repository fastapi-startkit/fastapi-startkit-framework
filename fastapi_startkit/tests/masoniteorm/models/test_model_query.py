"""
Tests for QueryBuilder behaviour: where, or_where, where_in, select,
limit, first_or_create, insert (bulk), and query-level update/delete.

All tests run against an in-memory SQLite database so they are
self-contained and require no external services.
"""

import pytest

from fastapi_startkit.carbon import Carbon
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.fields import DateTimeField
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
        is_admin: bool
        email_verified_at: Carbon = DateTimeField(fmt="%Y-%m-%d %H:%M:%S", tz="UTC")

    User.db_manager = db
    return User


@pytest.fixture
async def users_table(db, UserModel):
    """Create users table, yield, then drop it."""
    schema = db.get_schema_builder()
    await schema.drop_table_if_exists("users")
    async with await schema.on("default").create("users") as table:
        table.id()
        table.string("name")
        table.string("email").unique()
        table.boolean("is_admin").default(False)
        table.timestamp("email_verified_at").nullable()
        table.timestamps()
    yield schema
    await schema.drop_table_if_exists("users")


@pytest.fixture
async def seeded_users(UserModel, users_table):
    """Insert three users and return them as a list."""
    await UserModel.query().insert(
        [
            {"name": "Alice", "email": "alice@example.com", "is_admin": True},
            {"name": "Bob", "email": "bob@example.com", "is_admin": False},
            {"name": "Charlie", "email": "charlie@example.com", "is_admin": False},
        ]
    )
    return await UserModel.query().get()


# ---------------------------------------------------------------------------
# WHERE
# ---------------------------------------------------------------------------


class TestWhere:
    async def test_where_equals(self, UserModel, seeded_users):
        results = await UserModel.where("name", "Alice").get()
        assert len(results) == 1
        assert results.first().name == "Alice"

    async def test_where_with_explicit_operator(self, UserModel, seeded_users):
        results = await UserModel.where("name", "!=", "Alice").get()
        assert len(results) == 2

    async def test_where_like(self, UserModel, seeded_users):
        results = await UserModel.where("name", "like", "%li%").get()
        # Matches "Alice" and "Charlie"
        assert len(results) == 2

    async def test_where_chained(self, UserModel, seeded_users):
        results = await UserModel.where("is_admin", False).where("name", "Bob").get()
        assert len(results) == 1
        assert results.first().name == "Bob"

    async def test_where_dict(self, UserModel, seeded_users):
        results = await UserModel.where({"name": "Alice", "is_admin": True}).get()
        assert len(results) == 1

    async def test_where_returns_empty_collection_when_no_match(self, UserModel, seeded_users):
        results = await UserModel.where("name", "Nobody").get()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# OR WHERE
# ---------------------------------------------------------------------------


class TestOrWhere:
    async def test_or_where_matches_either_condition(self, UserModel, seeded_users):
        results = await UserModel.where("name", "Alice").or_where("name", "Bob").get()
        names = {u.name for u in results}
        assert names == {"Alice", "Bob"}

    async def test_or_where_no_match_returns_empty(self, UserModel, seeded_users):
        results = await UserModel.where("name", "Nobody").or_where("name", "Ghost").get()
        assert len(results) == 0

    async def test_or_where_like(self, UserModel, seeded_users):
        # Match names starting with 'A' OR ending with 'e'
        results = await UserModel.where("name", "like", "A%").or_where("name", "like", "%e").get()
        names = {u.name for u in results}
        # "Alice" matches both; "Charlie" matches '%e'
        assert "Alice" in names
        assert "Charlie" in names


# ---------------------------------------------------------------------------
# WHERE IN
# ---------------------------------------------------------------------------


class TestWhereIn:
    async def test_where_in_matches_list(self, UserModel, seeded_users):
        results = await UserModel.query().where_in("name", ["Alice", "Charlie"]).get()
        names = {u.name for u in results}
        assert names == {"Alice", "Charlie"}

    async def test_where_in_empty_list_returns_empty(self, UserModel, seeded_users):
        results = await UserModel.query().where_in("name", []).get()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------


class TestSelect:
    async def test_select_single_column(self, UserModel, seeded_users):
        results = await UserModel.query().select("name").get()
        first = results.first()
        assert first.name is not None
        # id was not selected — should be None or missing
        assert getattr(first, "email", None) is None

    async def test_select_multiple_columns(self, UserModel, seeded_users):
        results = await UserModel.query().select("name", "email").get()
        first = results.first()
        assert first.name is not None
        assert first.email is not None


# ---------------------------------------------------------------------------
# LIMIT
# ---------------------------------------------------------------------------


class TestLimit:
    async def test_limit_restricts_result_count(self, UserModel, seeded_users):
        results = await UserModel.query().limit(2).get()
        assert len(results) == 2

    async def test_limit_one_equals_first(self, UserModel, seeded_users):
        by_limit = await UserModel.query().limit(1).get()
        by_first = await UserModel.first()
        assert by_limit.first().id == by_first.id


# ---------------------------------------------------------------------------
# FIRST
# ---------------------------------------------------------------------------


class TestFirst:
    async def test_first_returns_single_model(self, UserModel, seeded_users):
        user = await UserModel.first()
        assert isinstance(user, UserModel)

    async def test_first_returns_none_when_empty(self, UserModel, users_table):
        user = await UserModel.first()
        assert user is None

    async def test_first_with_where(self, UserModel, seeded_users):
        user = await UserModel.where("name", "Bob").first()
        assert user is not None
        assert user.name == "Bob"


# ---------------------------------------------------------------------------
# FIND
# ---------------------------------------------------------------------------


class TestFind:
    async def test_find_by_primary_key(self, UserModel, seeded_users):
        first_user = await UserModel.first()
        found = await UserModel.find(first_user.id)
        assert found is not None
        assert found.id == first_user.id

    async def test_find_returns_none_for_missing_id(self, UserModel, seeded_users):
        found = await UserModel.find(99999)
        assert found is None


# ---------------------------------------------------------------------------
# FIRST OR CREATE
# ---------------------------------------------------------------------------


class TestFirstOrCreate:
    async def test_first_or_create_returns_existing(self, UserModel, seeded_users):
        user, created = None, False
        existing = await UserModel.where("email", "alice@example.com").first()
        result = await UserModel.query().first_or_create(
            {"email": "alice@example.com"},
            {"name": "Alice New"},
        )
        # Should return the existing record, not create a new one
        assert result.id == existing.id
        assert result.name == "Alice"

    async def test_first_or_create_inserts_when_missing(self, UserModel, users_table):
        user = await UserModel.query().first_or_create(
            {"email": "new@example.com"},
            {"name": "New User"},
        )
        assert user.id is not None
        assert user.email == "new@example.com"
        assert user.name == "New User"

        # Calling again should return the same record
        user2 = await UserModel.query().first_or_create(
            {"email": "new@example.com"},
        )
        assert user2.id == user.id


# ---------------------------------------------------------------------------
# BULK INSERT
# ---------------------------------------------------------------------------


class TestBulkInsert:
    async def test_insert_list_of_dicts(self, UserModel, users_table):
        await UserModel.query().insert(
            [
                {"name": "Dave", "email": "dave@example.com"},
                {"name": "Eve", "email": "eve@example.com"},
            ]
        )
        results = await UserModel.query().get()
        assert len(results) == 2

    async def test_insert_single_dict(self, UserModel, users_table):
        await UserModel.query().insert({"name": "Frank", "email": "frank@example.com"})
        results = await UserModel.query().get()
        assert len(results) == 1

    async def test_insert_empty_list_is_noop(self, UserModel, users_table):
        result = await UserModel.query().insert([])
        assert result is None
        results = await UserModel.query().get()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# QUERY-LEVEL UPDATE
# ---------------------------------------------------------------------------


class TestQueryUpdate:
    async def test_update_all_records(self, UserModel, seeded_users):
        await UserModel.query().update({"is_admin": True})
        results = await UserModel.where("is_admin", True).get()
        assert len(results) == 3

    async def test_update_with_where_filter(self, UserModel, seeded_users):
        await UserModel.where("name", "Bob").update({"name": "Robert"})
        bob = await UserModel.where("name", "Robert").first()
        assert bob is not None
        assert bob.name == "Robert"

        old_bob = await UserModel.where("name", "Bob").first()
        assert old_bob is None


# ---------------------------------------------------------------------------
# COMBINED SCENARIOS
# ---------------------------------------------------------------------------


class TestCombinedQueries:
    async def test_where_and_limit(self, UserModel, seeded_users):
        results = await UserModel.where("is_admin", False).limit(1).get()
        assert len(results) == 1

    async def test_where_and_select(self, UserModel, seeded_users):
        results = await UserModel.where("is_admin", True).select("name").get()
        assert len(results) == 1
        assert results.first().name == "Alice"

    async def test_or_where_and_limit(self, UserModel, seeded_users):
        results = await UserModel.where("name", "Alice").or_where("name", "Charlie").limit(1).get()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# OR WHERE NULL / OR WHERE NOT NULL
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_users_mixed_null(UserModel, users_table):
    """
    Insert three users where Alice has a verified_at timestamp and
    Bob/Charlie do not, so we can test NULL / NOT NULL branching.

    All dicts must have the same keys for the bulk-insert to work.
    """
    await UserModel.query().insert(
        [
            {
                "name": "Alice",
                "email": "alice@example.com",
                "is_admin": True,
                "email_verified_at": "2024-01-01 00:00:00",
            },
            {
                "name": "Bob",
                "email": "bob@example.com",
                "is_admin": False,
                "email_verified_at": None,
            },
            {
                "name": "Charlie",
                "email": "charlie@example.com",
                "is_admin": False,
                "email_verified_at": None,
            },
        ]
    )
    return await UserModel.query().get()


class TestOrWhereNull:
    async def test_or_where_null_returns_combined_rows(self, UserModel, seeded_users_mixed_null):
        # Bob and Charlie have NULL email_verified_at.
        # where(name=Alice) OR email_verified_at IS NULL → all three rows.
        results = await UserModel.where("name", "Alice").or_where_null("email_verified_at").get()
        names = {u.name for u in results}
        assert names == {"Alice", "Bob", "Charlie"}

    async def test_or_where_null_with_no_base_where(self, UserModel, seeded_users_mixed_null):
        # No leading where — just or_where_null still matches all NULL rows.
        results = await UserModel.query().or_where_null("email_verified_at").get()
        names = {u.name for u in results}
        assert "Bob" in names
        assert "Charlie" in names

    async def test_or_where_null_does_not_lose_base_match(self, UserModel, seeded_users_mixed_null):
        # where(name=Alice) alone returns 1; OR NULL adds the two un-verified users.
        base = await UserModel.where("name", "Alice").get()
        assert len(base) == 1

        combined = await UserModel.where("name", "Alice").or_where_null("email_verified_at").get()
        assert len(combined) == 3


class TestOrWhereNotNull:
    async def test_or_where_not_null_returns_combined_rows(self, UserModel, seeded_users_mixed_null):
        # Only Alice has a non-NULL email_verified_at.
        # where(name=Bob) OR email_verified_at IS NOT NULL → Alice + Bob
        results = await UserModel.where("name", "Bob").or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        assert names == {"Alice", "Bob"}

    async def test_or_where_not_null_with_no_base_where(self, UserModel, seeded_users_mixed_null):
        # No leading where — only Alice is non-null.
        results = await UserModel.query().or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        assert "Alice" in names

    async def test_or_where_not_null_excludes_null_only_rows(self, UserModel, seeded_users_mixed_null):
        # where(name=Nobody) OR email_verified_at IS NOT NULL → only Alice
        results = await UserModel.where("name", "Nobody").or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        assert names == {"Alice"}


# ---------------------------------------------------------------------------
# WHERE RAW
# ---------------------------------------------------------------------------


class TestWhereRaw:
    async def test_where_raw_with_binding(self, UserModel, seeded_users):
        results = await UserModel.where_raw("name = ?", bindings=("Alice",)).get()
        assert len(results) == 1
        assert results[0].name == "Alice"

    async def test_where_raw_without_bindings(self, UserModel, seeded_users):
        # SQLite uses standard SQL; filter admins without a binding.
        results = await UserModel.where_raw("is_admin = 1").get()
        assert len(results) == 1
        assert results[0].name == "Alice"

    async def test_where_raw_chained_with_where(self, UserModel, seeded_users):
        # Normal where then raw — AND logic applies.
        results = await UserModel.where("is_admin", False).where_raw("name = ?", bindings=("Bob",)).get()
        assert len(results) == 1
        assert results[0].name == "Bob"

    async def test_where_raw_no_match_returns_empty(self, UserModel, seeded_users):
        results = await UserModel.where_raw("name = ?", bindings=("Nobody",)).get()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# OR WHERE RAW
# ---------------------------------------------------------------------------


class TestOrWhereRaw:
    async def test_or_where_raw_with_binding(self, UserModel, seeded_users):
        results = (
            await UserModel.where("name", "Alice").or_where_raw("name = ?", bindings=("Bob",)).get()
        )
        names = {r.name for r in results}
        assert names == {"Alice", "Bob"}

    async def test_or_where_raw_no_bindings(self, UserModel, seeded_users):
        # Reproduces the original production scenario: no bindings arg provided.
        # Must not raise AttributeError on tuple vs list.
        results = await UserModel.where("name", "Alice").or_where_raw("name IS NOT NULL").get()
        assert len(results) > 0

    async def test_or_where_raw_three_way_union(self, UserModel, seeded_users):
        # where(Alice) OR raw(Bob) OR raw(Charlie) → all three rows
        results = (
            await UserModel.where("name", "Alice")
            .or_where_raw("name = ?", bindings=("Bob",))
            .or_where_raw("name = ?", bindings=("Charlie",))
            .get()
        )
        names = {r.name for r in results}
        assert names == {"Alice", "Bob", "Charlie"}

    async def test_or_where_raw_no_match_returns_only_base(self, UserModel, seeded_users):
        results = (
            await UserModel.where("name", "Alice").or_where_raw("name = ?", bindings=("Nobody",)).get()
        )
        names = {r.name for r in results}
        assert names == {"Alice"}

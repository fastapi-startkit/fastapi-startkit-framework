from unittest.mock import AsyncMock

from sqlalchemy.dialects import sqlite

from ..fixtures.db import DB
from ...fixtures.model import User
from ..test_case import TestCase


class TestQueryBuilderUpsert(TestCase):
    async def test_upsert_inserts_new_records(self):
        affected = await User.upsert(
            [
                {"email": "u1@test.com", "name": "U1", "is_admin": False},
                {"email": "u2@test.com", "name": "U2", "is_admin": True},
            ],
            unique_by="email",
        )
        assert affected >= 1

        u1 = await User.where("email", "u1@test.com").first()
        u2 = await User.where("email", "u2@test.com").first()
        assert u1.name == "U1"
        assert u2.name == "U2"
        assert u2.is_admin is True

    async def test_upsert_updates_existing_on_conflict(self):
        await User.upsert({"email": "dup@test.com", "name": "Original", "is_admin": False}, unique_by="email")
        await User.upsert({"email": "dup@test.com", "name": "Updated", "is_admin": True}, unique_by="email")

        rows = await User.where("email", "dup@test.com").get()
        assert len(rows) == 1
        assert rows.first().name == "Updated"
        assert rows.first().is_admin is True

    async def test_upsert_respects_update_subset(self):
        await User.upsert({"email": "sub@test.com", "name": "Keep", "is_admin": False}, unique_by="email")
        # Only ``is_admin`` is listed for update, so ``name`` must remain unchanged.
        await User.upsert(
            {"email": "sub@test.com", "name": "Ignored", "is_admin": True},
            unique_by="email",
            update=["is_admin"],
        )

        user = await User.where("email", "sub@test.com").first()
        assert user.name == "Keep"
        assert user.is_admin is True

    async def test_upsert_refreshes_updated_at_on_update_branch(self):
        # Explicit updated_at is honoured on the INSERT branch.
        await User.upsert(
            {"email": "ts@test.com", "name": "TS", "is_admin": False, "updated_at": "2000-01-01 00:00:00"},
            unique_by="email",
        )
        before = await User.where("email", "ts@test.com").first()
        assert before.updated_at.year == 2000

        # __timestamps__ is enabled on User, so the UPDATE branch refreshes updated_at.
        await User.upsert({"email": "ts@test.com", "name": "TS2", "is_admin": False}, unique_by="email")
        after = await User.where("email", "ts@test.com").first()
        assert after.name == "TS2"
        assert after.updated_at.year != 2000

    async def test_upsert_emits_single_on_conflict_statement(self):
        captured = AsyncMock(return_value=2)
        DB.connection("sqlite").upsert = captured

        await User.query().upsert(
            [{"email": "a@test.com", "name": "A"}, {"email": "b@test.com", "name": "B"}],
            unique_by="email",
        )

        captured.assert_called_once()
        (statement,) = captured.call_args[0]
        compiled = str(statement.compile(dialect=sqlite.dialect()))
        # A single multi-row VALUES clause with a sqlite ON CONFLICT ... excluded update.
        assert compiled.count("INSERT INTO") == 1
        assert "ON CONFLICT (email)" in compiled
        assert "excluded.name" in compiled

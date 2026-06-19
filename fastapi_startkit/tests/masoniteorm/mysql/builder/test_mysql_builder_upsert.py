from unittest.mock import AsyncMock

from sqlalchemy.dialects import mysql

from ..test_case import TestCase
from ..fixtures.db import DB
from ...fixtures.model import User


class TestMySQLQueryBuilderUpsert(TestCase):
    """MySQL upsert compiles to a single ON DUPLICATE KEY UPDATE statement.

    Mirrors the other MySQL builder tests, which assert generated SQL without a
    live server.
    """

    def _compile(self, statement):
        return str(statement.compile(dialect=mysql.dialect()))

    async def test_upsert_compiles_on_duplicate_key_update(self):
        statement = User.query()._build_upsert_statement(
            [
                {"email": "a@test.com", "name": "A", "is_admin": False},
                {"email": "b@test.com", "name": "B", "is_admin": True},
            ],
            ["email"],
            None,
        )

        compiled = self._compile(statement)
        # Single multi-row INSERT with a MySQL-style ON DUPLICATE KEY UPDATE.
        assert compiled.count("INSERT INTO") == 1
        assert "ON DUPLICATE KEY UPDATE" in compiled
        assert "name = VALUES(name)" in compiled
        assert "is_admin = VALUES(is_admin)" in compiled
        # The conflict key is never part of the update set.
        assert "email = VALUES(email)" not in compiled

    async def test_upsert_respects_explicit_update_columns(self):
        statement = User.query()._build_upsert_statement(
            [{"email": "a@test.com", "name": "A", "is_admin": False}],
            ["email"],
            ["name"],
        )

        compiled = self._compile(statement)
        assert "name = VALUES(name)" in compiled
        assert "is_admin = VALUES(is_admin)" not in compiled

    async def test_upsert_invokes_connection_once(self):
        captured = AsyncMock(return_value=2)
        DB.connection("mysql").upsert = captured

        await User.query().upsert(
            [{"email": "a@test.com", "name": "A"}, {"email": "b@test.com", "name": "B"}],
            unique_by="email",
        )

        captured.assert_called_once()

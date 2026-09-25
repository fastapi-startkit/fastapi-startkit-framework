from fastapi_startkit.masoniteorm.connections.connection import Connection
from fastapi_startkit.masoniteorm.models import Model

from ..fixtures.model import User
from .test_case import TestCase


class TestConnectionSelect(TestCase):
    async def test_select_returns_plain_dicts(self):
        await User.create({"email": "select@example.com", "name": "Select", "is_admin": False})

        rows = await Model.db_manager.connection(None).select(
            "SELECT email, name FROM users WHERE email = ?", ["select@example.com"]
        )

        assert rows == [{"email": "select@example.com", "name": "Select"}]
        assert all(type(row) is dict for row in rows)

    def test_base_connection_has_no_grammar_or_processor(self):
        assert Connection.get_query_grammar() is None
        assert Connection.get_post_processor() is None

# pyright: reportUnknownMemberType=error, reportUnknownVariableType=error, reportUnknownArgumentType=error
"""Static typing guarantees of where() and get() on models and the query builder.

The type checker is the real assertion here:

    cd fastapi_startkit && uv run pyright -p pyrightconfig.typing-tests.json

(the repo pyright config excludes tests/, so this file ships its own config).

`assert_type` is a no-op at runtime, so every static assertion is paired with a
runtime check that the value really is what the annotation promises. The
`reportUnknown*` rules above are enabled per-file: an unannotated parameter on
where()/get() makes this module fail to type-check even though the assert_type
calls themselves would still pass.
"""

from typing import assert_type

from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

from ...fixtures.model import User
from ..test_case import TestCase


class TestWhereTyping(TestCase):
    async def test_value_form_returns_builder_of_the_model(self):
        builder = User.where("name", "Joe")

        assert_type(builder, QueryBuilder[User])
        assert isinstance(builder, QueryBuilder)

    async def test_operator_form_returns_builder_of_the_model(self):
        builder = User.where("name", "!=", "Joe")

        assert_type(builder, QueryBuilder[User])
        assert isinstance(builder, QueryBuilder)

    async def test_dict_form_returns_builder_of_the_model(self):
        builder = User.where({"name": "Joe", "is_admin": True})

        assert_type(builder, QueryBuilder[User])
        assert isinstance(builder, QueryBuilder)

    async def test_callable_form_returns_builder_of_the_model(self):
        builder = User.query().where(lambda q: q.where("name", "Joe").where("is_admin", True))

        assert_type(builder, QueryBuilder[User])
        assert isinstance(builder, QueryBuilder)

    async def test_model_type_survives_a_multi_step_chain(self):
        builder = User.where("is_admin", True).where("name", "!=", "Jane").where("name", "like", "%o%")

        assert_type(builder, QueryBuilder[User])
        assert isinstance(builder, QueryBuilder)


class TestGetTyping(TestCase):
    async def test_awaited_get_is_a_collection_of_the_model(self):
        users = await User.where("name", "Joe").get()

        assert_type(users, Collection[User])
        assert isinstance(users, Collection)
        assert len(users) == 1

    async def test_collection_elements_are_the_model(self):
        users = await User.where("name", "Joe").get()
        user = users.first()

        assert_type(user, User | None)
        assert isinstance(user, User)
        assert user.name == "Joe"

    async def test_get_with_explicit_columns(self):
        users = await User.where("name", "Joe").get(["name"])

        assert_type(users, Collection[User])
        user = users.first()
        assert user is not None
        assert user.name == "Joe"

    async def test_model_get_is_a_collection_of_the_model(self):
        users = await User.get()

        assert_type(users, Collection[User])
        assert len(users) == 2

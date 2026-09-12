"""Typing guarantees of Container.make().

The `assert_type` calls here are checked statically:

    uv run pyright tests/core/test_container_typing.py

They are no-ops at runtime, so each one is paired with a runtime assertion that
the value really is what the annotation promises.
"""

from typing import Any, assert_type

import pytest

from fastapi_startkit.container.container import Container
from fastapi_startkit.exceptions import MissingContainerBindingNotFound


class Mailer:
    def send(self) -> str:
        return "sent"


@pytest.fixture
def container() -> Container:
    return Container()


class TestMakeTyping:
    def test_class_key_resolves_to_that_class(self, container: Container):
        container.bind(Mailer, Mailer())

        mailer = container.make(Mailer)

        assert_type(mailer, Mailer)
        assert isinstance(mailer, Mailer)
        assert mailer.send() == "sent"

    def test_unbound_class_key_still_resolves_to_that_class(self, container: Container):
        mailer = container.make(Mailer)

        assert_type(mailer, Mailer)
        assert isinstance(mailer, Mailer)

    def test_string_key_stays_any(self, container: Container):
        container.bind("mailer", Mailer())

        mailer = container.make("mailer")

        assert_type(mailer, Any)
        assert isinstance(mailer, Mailer)

    def test_missing_string_key_raises_instead_of_returning_none(self, container: Container):
        with pytest.raises(MissingContainerBindingNotFound):
            container.make("nope")

    def test_instance_returns_a_container(self):
        original = Container._instance
        try:
            c = Container()
            Container.set_instance(c)

            assert_type(Container.instance(), Container)
            assert Container.instance() is c
        finally:
            Container._instance = original

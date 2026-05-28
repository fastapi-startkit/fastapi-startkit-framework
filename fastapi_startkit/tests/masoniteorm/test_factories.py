"""Tests for ORM Factory (task #16).

Tests the Factory base class using mocked models to avoid needing
a live database connection.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_startkit.masoniteorm.factory.factory import Factory


# ---------------------------------------------------------------------------
# Minimal concrete factory for testing
# ---------------------------------------------------------------------------


class ConcreteFactory(Factory):
    model = MagicMock()

    def definition(self) -> dict:
        return {"name": "Test User", "email": "test@example.com"}


class AnotherFactory(Factory):
    model = MagicMock()

    def definition(self) -> dict:
        return {"title": "Post Title", "body": "Post body content"}


# ---------------------------------------------------------------------------
# Factory — unit tests with mocked model
# ---------------------------------------------------------------------------


class TestFactoryDefinition:
    def test_definition_returns_dict(self):
        factory = ConcreteFactory()
        result = factory.definition()
        assert isinstance(result, dict)
        assert "name" in result
        assert "email" in result

    def test_definition_values(self):
        factory = ConcreteFactory()
        d = factory.definition()
        assert d["name"] == "Test User"
        assert d["email"] == "test@example.com"

    def test_another_factory_definition(self):
        factory = AnotherFactory()
        d = factory.definition()
        assert d["title"] == "Post Title"


class TestFactoryCreate:
    @pytest.mark.asyncio
    async def test_create_calls_model_create(self):
        mock_instance = MagicMock()
        mock_instance.id = 1
        mock_instance.name = "Test User"

        ConcreteFactory.model = MagicMock()
        ConcreteFactory.model.create = AsyncMock(return_value=mock_instance)

        result = await ConcreteFactory.create()

        ConcreteFactory.model.create.assert_called_once_with({"name": "Test User", "email": "test@example.com"})
        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_create_returns_model_instance(self):
        mock_user = MagicMock()
        mock_user.name = "Test User"

        ConcreteFactory.model = MagicMock()
        ConcreteFactory.model.create = AsyncMock(return_value=mock_user)

        result = await ConcreteFactory.create()
        assert result.name == "Test User"

    @pytest.mark.asyncio
    async def test_create_uses_definition_data(self):
        captured_data = {}

        async def capture_create(data):
            captured_data.update(data)
            return MagicMock()

        ConcreteFactory.model = MagicMock()
        ConcreteFactory.model.create = capture_create

        await ConcreteFactory.create()

        assert captured_data["name"] == "Test User"
        assert captured_data["email"] == "test@example.com"


class TestFactoryAbstract:
    def test_cannot_instantiate_abstract_factory(self):
        """Factory without definition() cannot be instantiated."""
        with pytest.raises(TypeError):
            Factory()

    def test_concrete_factory_can_be_instantiated(self):
        f = ConcreteFactory()
        assert f is not None


# ---------------------------------------------------------------------------
# Factory — verify model attribute is used (not hardcoded)
# ---------------------------------------------------------------------------


class TestFactoryModelBinding:
    @pytest.mark.asyncio
    async def test_create_uses_class_model_attribute(self):
        class PostFactory(Factory):
            model = MagicMock()

            def definition(self):
                return {"title": "Hello"}

        PostFactory.model.create = AsyncMock(return_value=MagicMock(title="Hello"))

        result = await PostFactory.create()
        PostFactory.model.create.assert_called_once_with({"title": "Hello"})

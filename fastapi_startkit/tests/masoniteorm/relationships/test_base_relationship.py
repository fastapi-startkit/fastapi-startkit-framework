from unittest.mock import MagicMock

import pytest

from fastapi_startkit.masoniteorm.models import registry
from fastapi_startkit.masoniteorm.relationships.BaseRelationship import BaseRelationship

from .conftest import make_builder


def test_rejects_non_string_relationship_name():
    with pytest.raises(TypeError, match="expects a string"):
        BaseRelationship(["not", "a", "string"])


def test_stores_keys_and_defaults():
    rel = BaseRelationship("Profile", local_key="id", foreign_key="user_id")

    assert rel.local_key == "id"
    assert rel.foreign_key == "user_id"
    assert rel.attribute is None


def test_set_name_records_attribute_and_owner():
    rel = BaseRelationship("Profile")

    class Owner:
        pass

    rel.__set_name__(Owner, "profile")

    assert rel.attribute == "profile"
    assert rel.owner_class is Owner


def test_get_builder_resolves_through_registry(monkeypatch):
    related_builder = object()
    related_instance = MagicMock()
    related_instance.get_builder.return_value = related_builder
    related_model = MagicMock(return_value=related_instance)

    monkeypatch.setattr(registry.Registry, "resolve", classmethod(lambda cls, name: related_model))

    rel = BaseRelationship("Profile")

    assert rel.get_builder() is related_builder


def test_get_returns_self_when_accessed_on_class():
    rel = BaseRelationship("Profile")

    assert rel.__get__(None, object) is rel


def test_get_returns_self_when_owner_not_loaded():
    rel = BaseRelationship("Profile")
    rel.attribute = "profile"
    rel.set_keys = MagicMock()

    instance = MagicMock()
    instance.is_loaded.return_value = False

    assert rel.__get__(instance, object) is rel
    rel.set_keys.assert_called_once_with(instance, "profile")


def test_get_returns_cached_relationship():
    rel = BaseRelationship("Profile")
    rel.attribute = "profile"
    rel.set_keys = MagicMock()

    instance = MagicMock()
    instance.is_loaded.return_value = True
    instance._relationships = {"profile": "cached"}

    assert rel.__get__(instance, object) == "cached"


def test_getattr_delegates_to_builder():
    builder = make_builder()
    builder.custom_attr = "delegated"

    rel = BaseRelationship("Profile")
    rel.get_builder = MagicMock(return_value=builder)

    assert rel.custom_attr == "delegated"


def test_joins_builds_join_clause():
    other = make_builder(table_name="profiles")
    local = make_builder(table_name="users")

    rel = BaseRelationship("Profile", local_key="id", foreign_key="user_id")
    rel.get_builder = MagicMock(return_value=other)

    rel.joins(local, clause="left")

    local.join.assert_called_once_with(
        "profiles",
        "users.id",
        "=",
        "profiles.user_id",
        clause="left",
    )


@pytest.mark.parametrize(
    "method,args",
    [
        ("apply_query", (MagicMock(), MagicMock())),
        ("query_where_exists", (MagicMock(), MagicMock())),
        ("get_with_count_query", (MagicMock(), MagicMock())),
        ("attach", (MagicMock(), MagicMock())),
        ("get_related", (MagicMock(), MagicMock())),
        ("relate", (MagicMock(),)),
        ("detach", (MagicMock(), MagicMock())),
        ("attach_related", (MagicMock(), MagicMock())),
        ("detach_related", (MagicMock(), MagicMock())),
        ("query_has", (MagicMock(),)),
        ("map_related", (MagicMock(),)),
    ],
)
def test_abstract_methods_raise_not_implemented(method, args):
    rel = BaseRelationship("Profile")

    with pytest.raises(NotImplementedError):
        getattr(rel, method)(*args)

"""Unit tests for the polymorphic relationships (MorphOne/MorphMany/MorphToMany/MorphTo).

``MorphOne`` and ``MorphToMany`` are tested with mocks because their
``morph_map()`` implementations reference an undefined ``load_config`` name
(``MorphOne.py`` line 134, ``MorphToMany.py`` line 103) and raise ``NameError``
when called for real. ``MorphMany`` is likewise mocked: its resolved builder is
not wired to this fork's async ``QueryBuilder``. ``MorphTo`` does work against
real sqlite and is additionally covered end-to-end in
``sqlite/relationships/test_sqlite_polymorphic.py``. The framework fixes needed
for real-DB coverage of the other morphs are tracked in the project backlog.
"""

from unittest.mock import MagicMock

import pytest

from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models import registry
from fastapi_startkit.masoniteorm.relationships.MorphOne import MorphOne
from fastapi_startkit.masoniteorm.relationships.MorphMany import MorphMany
from fastapi_startkit.masoniteorm.relationships.MorphToMany import MorphToMany
from fastapi_startkit.masoniteorm.relationships.MorphTo import MorphTo


class Article:
    __primary_key__ = "id"

    def __init__(self, pk=1):
        self.id = pk
        self.record_type = "article"
        self.record_id = pk
        self._pk = pk

    def serialize(self):
        return {"id": self._pk, "record_type": "article", "record_id": self._pk}

    def get_primary_key(self):
        return "id"

    def get_primary_key_value(self):
        return self._pk


def morph_builder(table_name="likes"):
    builder = MagicMock(name="polymorphic_builder")
    for method in ("where", "where_in"):
        getattr(builder, method).return_value = builder
    builder.get.return_value = "GET_RESULT"
    builder.first.return_value = "FIRST_RESULT"
    builder.get_table_name.return_value = table_name
    return builder


# --------------------------------------------------------------------------- #
# MorphMany
# --------------------------------------------------------------------------- #
def test_morph_many_init_and_set_keys():
    rel = MorphMany(lambda self: None, morph_key=None, morph_id=None)
    rel.set_keys(None, None)

    assert rel.morph_id == "record_id"
    assert rel.morph_key == "record_type"


def test_morph_many_get_record_key_lookup():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}

    assert rel.get_record_key_lookup(Article()) == "article"


def test_morph_many_get_record_key_lookup_raises_when_unknown():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {}

    with pytest.raises(ValueError, match="record type key"):
        rel.get_record_key_lookup(Article())


def test_morph_many_apply_query_filters_by_type_and_id():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    owner_builder = MagicMock()
    owner_builder._model = Article()
    instance = MagicMock()
    instance.get_primary_key_value.return_value = 7

    result = rel.apply_query(owner_builder, instance)

    assert result == "GET_RESULT"
    rel.polymorphic_builder.where.assert_any_call("record_type", "article")


def test_morph_many_get_related_single():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    result = rel.get_related(None, Article(3))

    builder = rel.polymorphic_builder
    assert result == "GET_RESULT"
    builder.where.assert_any_call("record_type", "article")
    builder.where.assert_any_call("record_id", 3)
    builder.get.assert_called_once()


def test_morph_many_get_related_single_with_callback():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()
    callback = MagicMock(return_value=morph_builder())

    result = rel.get_related(None, Article(3), callback=callback)

    builder = rel.polymorphic_builder
    # The callback receives the fully-filtered builder, not a bare mock.
    callback.assert_called_once_with(builder)
    builder.where.assert_any_call("record_type", "article")
    builder.where.assert_any_call("record_id", 3)
    assert result == "GET_RESULT"


def test_morph_many_get_related_collection():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    relation = Collection([Article(1), Article(2)])
    result = rel.get_related(None, relation)

    builder = rel.polymorphic_builder
    assert result == "GET_RESULT"
    builder.where.assert_called_once_with("likes.record_type", "article")
    where_in_args = builder.where_in.call_args.args
    assert where_in_args[0] == "record_id"
    assert list(where_in_args[1]) == [1, 2]
    builder.get.assert_called_once()


def test_morph_many_register_related():
    rel = MorphMany(lambda self: None)
    rel.morph_map = lambda: {"article": Article}

    collection = MagicMock()
    collection.where.return_value = collection

    model = MagicMock()
    model.__class__ = Article
    model.get_primary_key_value.return_value = 5

    rel.register_related("likes", model, collection)

    model.add_relation.assert_called_once_with({"likes": collection})


def test_morph_many_morph_map_reads_registry(monkeypatch):
    monkeypatch.setattr(registry.Registry, "get_morph_map", classmethod(lambda cls: {"article": Article}))
    rel = MorphMany(lambda self: None)

    assert rel.morph_map() == {"article": Article}


# --------------------------------------------------------------------------- #
# MorphOne
# --------------------------------------------------------------------------- #
def test_morph_one_init_with_string_shifts_keys():
    rel = MorphOne("likeable_type", "likeable_id")

    assert rel.fn is None
    assert rel.morph_key == "likeable_type"
    assert rel.morph_id == "likeable_id"


def test_morph_one_init_with_callable_keeps_defaults():
    rel = MorphOne(lambda self: None)

    assert rel.morph_key == "record_type"
    assert rel.morph_id == "record_id"


def test_morph_one_apply_query_returns_first():
    rel = MorphOne(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    owner_builder = MagicMock()
    owner_builder._model = Article()
    instance = MagicMock()
    instance.get_primary_key_value.return_value = 2

    result = rel.apply_query(owner_builder, instance)

    builder = rel.polymorphic_builder
    assert result == "FIRST_RESULT"
    builder.where.assert_any_call("record_type", "article")
    builder.where.assert_any_call("record_id", 2)
    # MorphOne resolves to a single row: .first(), never .get().
    builder.first.assert_called_once()
    builder.get.assert_not_called()


def test_morph_one_get_related_single():
    rel = MorphOne(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    result = rel.get_related(None, Article(4))

    builder = rel.polymorphic_builder
    assert result == "FIRST_RESULT"
    builder.where.assert_any_call("record_type", "article")
    builder.where.assert_any_call("record_id", 4)
    builder.first.assert_called_once()
    builder.get.assert_not_called()


def test_morph_one_get_related_collection():
    rel = MorphOne(lambda self: None)
    rel.morph_map = lambda: {"article": Article}
    rel.polymorphic_builder = morph_builder()

    relation = Collection([Article(1), Article(2)])
    result = rel.get_related(None, relation)

    builder = rel.polymorphic_builder
    assert result == "GET_RESULT"
    builder.where.assert_called_once_with("likes.record_type", "article")
    where_in_args = builder.where_in.call_args.args
    assert where_in_args[0] == "record_id"
    assert list(where_in_args[1]) == [1, 2]
    builder.get.assert_called_once()


def test_morph_one_register_related_uses_first():
    rel = MorphOne(lambda self: None)
    rel.morph_map = lambda: {"article": Article}

    collection = MagicMock()
    collection.where.return_value = collection
    collection.first.return_value = "related"

    model = MagicMock()
    model.__class__ = Article
    model.get_primary_key_value.return_value = 9

    rel.register_related("record", model, collection)

    model.add_relation.assert_called_once_with({"record": "related"})


# --------------------------------------------------------------------------- #
# MorphToMany
# --------------------------------------------------------------------------- #
def test_morph_to_many_init_with_string():
    rel = MorphToMany("likeable_type", "likeable_id")

    assert rel.fn is None
    assert rel.morph_key == "likeable_type"
    assert rel.morph_id == "likeable_id"


def test_morph_to_many_set_keys_defaults():
    rel = MorphToMany(lambda self: None, morph_key=None, morph_id=None)
    rel.set_keys(None, None)

    assert rel.morph_key == "record_type"
    assert rel.morph_id == "record_id"


def test_morph_to_many_apply_query():
    model = MagicMock()
    model.get_primary_key.return_value = "id"
    model.where.return_value.first.return_value = "MODEL"

    rel = MorphToMany(lambda self: None)
    rel.morph_map = lambda: {"article": model}

    instance = MagicMock()
    instance.__attributes__ = {"record_type": "article", "record_id": 3}

    assert rel.apply_query(MagicMock(), instance) == "MODEL"
    model.where.assert_called_once_with("id", 3)


def test_morph_to_many_get_related_single():
    model = MagicMock()
    model.find.return_value = "FOUND"

    rel = MorphToMany(lambda self: None)
    rel.morph_map = lambda: {"article": model}

    relation = MagicMock()
    relation.record_type = "article"
    relation.record_id = 8

    assert rel.get_related(None, relation) == "FOUND"
    model.find.assert_called_once_with([8])


def test_morph_to_many_get_related_collection():
    morphed = MagicMock()
    morphed.get_primary_key.return_value = "id"
    morphed.get_table_name.return_value = "articles"
    morphed.where_in.return_value.get.return_value = [Article(1)]

    rel = MorphToMany(lambda self: None)
    rel.morph_map = lambda: {"article": morphed}

    relation = Collection(
        [
            {"record_type": "article", "record_id": 1},
            {"record_type": "article", "record_id": 2},
        ]
    )

    result = rel.get_related(None, relation)

    assert isinstance(result, Collection)
    morphed.where_in.assert_called_once()


def test_morph_to_many_register_related():
    morphed = MagicMock()
    morphed.get_primary_key.return_value = "id"

    rel = MorphToMany(lambda self: None)
    rel.morph_map = lambda: {"article": morphed}

    collection = MagicMock()
    collection.where.return_value = "scoped"

    model = MagicMock()
    model.record_type = "article"
    model.record_id = 4

    rel.register_related("record", model, collection)

    collection.where.assert_called_once_with("id", 4)
    model.add_relation.assert_called_once_with({"record": "scoped"})


# --------------------------------------------------------------------------- #
# MorphTo
# --------------------------------------------------------------------------- #
def test_morph_to_set_keys_defaults():
    rel = MorphTo("Like", morph_key=None, morph_id=None)
    rel.set_keys()

    assert rel.morph_key == "record_type"
    assert rel.morph_id == "record_id"


def test_morph_to_set_name_records_attribute():
    rel = MorphTo("Like")
    rel.__set_name__(object, "record")

    assert rel.attribute == "record"


def test_morph_to_apply_query():
    model = MagicMock()
    model.__primary_key__ = "id"
    model.where.return_value.first.return_value = "MODEL"

    rel = MorphTo("Like")
    rel.morph_map = lambda: {"article": model}

    instance = MagicMock()
    instance.__attributes__ = {"record_type": "article", "record_id": 6}

    assert rel.apply_query(MagicMock(), instance) == "MODEL"
    model.where.assert_called_once_with("id", 6)


def test_morph_to_register_related():
    morphed = MagicMock()
    morphed.__primary_key__ = "id"

    rel = MorphTo("Like")
    rel.morph_map = lambda: {"article": morphed}

    collection = MagicMock()
    collection.where.return_value.first.return_value = "related"

    model = MagicMock()
    model.record_type = "article"
    model.record_id = 5

    rel.register_related("record", model, collection)

    model.add_relation.assert_called_once_with({"record": "related"})


def test_morph_to_map_related_returns_input():
    rel = MorphTo("Like")
    payload = object()

    assert rel.map_related(payload) is payload


def test_morph_to_morph_map_reads_registry(monkeypatch):
    monkeypatch.setattr(registry.Registry, "get_morph_map", classmethod(lambda cls: {"article": Article}))
    rel = MorphTo("Like")

    assert rel.morph_map() == {"article": Article}


def test_morph_to_getattr_delegates_to_related_builder(monkeypatch):
    resolved_instance = MagicMock()
    resolved_instance._related_builder.some_attr = "delegated"
    resolved_model = MagicMock(return_value=resolved_instance)
    monkeypatch.setattr(registry.Registry, "resolve", classmethod(lambda cls, name: resolved_model))

    rel = MorphTo("Like")

    assert rel.some_attr == "delegated"


async def test_morph_to_get_related_collection(monkeypatch):
    from unittest.mock import AsyncMock

    morphed = MagicMock()
    morphed.__table__ = "articles"
    morphed.__primary_key__ = "id"
    morphed.where_in.return_value.get = AsyncMock(return_value=Collection([Article(1)]))

    rel = MorphTo("Like")
    rel.morph_map = lambda: {"article": morphed}

    relation = Collection(
        [
            {"record_type": "article", "record_id": 1},
            {"record_type": "article", "record_id": 2},
        ]
    )

    result = await rel.get_related(None, relation)

    assert isinstance(result, Collection)
    morphed.where_in.assert_called_once()

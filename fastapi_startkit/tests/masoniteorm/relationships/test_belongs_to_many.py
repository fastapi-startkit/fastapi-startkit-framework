"""Unit tests for :class:`BelongsToMany`, run against a mocked query builder.

These tests mock the query builder (see ``conftest.make_builder``) instead of
running against real sqlite because ``BelongsToMany`` is not currently wired to
this fork's async ``QueryBuilder``. A real many-to-many fixture already exists
(``Store``/``Product`` + the ``product_store`` pivot in ``fixtures/migration.py``),
so the blocker is framework wiring, not test data:

* The async ``QueryBuilder`` (``masoniteorm/models/builder.py``) does not implement
  ``table()``, ``without_global_scopes()`` or ``add_select()``, all of which
  ``BelongsToMany`` calls (e.g. ``BelongsToMany.py`` lines 78, 227, 463). Real
  access/eager-load/``where_has`` raise ``AttributeError``.
* ``BaseRelationship.get_builder()`` calls ``self.fn()`` with no arguments while
  ``BelongsToMany.__init__`` assigns ``self.fn = lambda x: ...``, so resolving the
  related builder raises ``TypeError: <lambda>() missing 1 required positional
  argument: 'x'``.
* ``attach``/``detach`` chain ``Pivot.on(...).table(...).without_global_scopes()
  .create(...)`` on a plain ``Pivot`` model that has none of those chainable
  builder methods, so the chain resolves to ``None`` and raises ``TypeError``.

Mocking the builder lets these tests exercise the relationship's own logic (key
inference, pivot hydration, join/select construction) in isolation. Wiring the
async ``QueryBuilder`` for real-DB coverage is tracked in the project backlog.
"""

from unittest.mock import MagicMock, patch


from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models import registry
from fastapi_startkit.masoniteorm.relationships.BelongsToMany import BelongsToMany

from .conftest import make_builder


def make_pivot_model(extra=None):
    model = MagicMock()
    model.store_product_id = 1
    model.m_reserved2 = 2
    model.m_reserved3 = 3
    model.m_reserved4 = "u"
    model.m_reserved5 = "c"
    if extra is not None:
        model.extra = extra
    model.__original_attributes__ = MagicMock()
    return model


def make_relationship(table="store_product", **kwargs):
    rel = BelongsToMany(
        "Product",
        local_foreign_key="store_id",
        other_foreign_key="product_id",
        local_owner_key="id",
        other_owner_key="id",
        table=table,
        **kwargs,
    )
    return rel


def test_init_resolves_string_name(monkeypatch):
    monkeypatch.setattr(registry.Registry, "resolve", classmethod(lambda cls, name: "resolved"))
    rel = BelongsToMany("Product")

    assert rel.fn("x") == "resolved"
    assert rel.local_owner_key == "id"
    assert rel.other_owner_key == "id"


def test_set_keys_applies_defaults():
    rel = BelongsToMany("Product")
    rel.local_key = None
    rel.foreign_key = None

    rel.set_keys(MagicMock(), "product")

    assert rel.local_key == "id"
    assert rel.foreign_key == "product_id"


def test_table_setter_is_chainable():
    rel = make_relationship()

    assert rel.table("custom_pivot") is rel
    assert rel._table == "custom_pivot"


def test_map_related_returns_input():
    rel = make_relationship()
    payload = object()

    assert rel.map_related(payload) is payload


def test_get_pivot_table_name_sorts_and_singularizes():
    rel = make_relationship()
    query = make_builder(table_name="stores")
    builder = make_builder(table_name="products")

    assert rel.get_pivot_table_name(query, builder) == "product_store"


def test_make_builder_applies_eager_loads():
    rel = make_relationship()
    query = make_builder()
    rel.get_builder = MagicMock(return_value=query)

    result = rel.make_builder(["images"])

    query.with_.assert_called_once_with(["images"])
    assert result is query


def test_register_related_adds_scoped_collection():
    rel = make_relationship()
    rel._table = "store_product"

    model = MagicMock()
    model.id = 5
    collection = MagicMock()
    collection.where.return_value = "scoped"

    rel.register_related("products", model, collection)

    collection.where.assert_called_once_with("store_product_id", 5)
    model.add_relation.assert_called_once_with({"products": "scoped"})


def test_joins_builds_inner_and_outer_joins():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    builder = make_builder(table_name="stores", columns=None)
    rel.joins(builder, clause="left")

    # No pre-existing columns → select clause added, then two joins.
    assert builder.select.called
    assert builder.join.call_count == 2


def test_query_has_delegates_to_builder_method():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    builder = make_builder(table_name="stores")
    rel.query_has(builder, method="where_exists")

    builder.where_exists.assert_called_once()


def test_query_where_exists_invokes_callback_and_method():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    builder = make_builder(table_name="stores")
    callback = MagicMock(return_value="sub")

    rel.query_where_exists(builder, callback, method="where_exists")

    callback.assert_called_once()
    builder.where_exists.assert_called_once()


def test_get_with_count_query_adds_select():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    builder = make_builder(table_name="stores", columns=["*"])
    rel.get_with_count_query(builder, callback=None)

    builder.add_select.assert_called_once()


def test_get_with_count_query_selects_star_when_no_columns():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    builder = make_builder(table_name="stores", columns=[])
    rel.get_with_count_query(builder, callback=None)

    builder.select.assert_called_once_with("*")


@patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot")
def test_attach_creates_pivot_record(pivot):
    rel = make_relationship()
    chain = pivot.on.return_value.table.return_value.without_global_scopes.return_value

    current = MagicMock()
    current.id = 1
    current.get_builder.return_value.connection = "sqlite"
    related = MagicMock()
    related.id = 9

    rel.attach(current, related)

    chain.create.assert_called_once_with({"store_id": 1, "product_id": 9})


@patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot")
def test_attach_includes_timestamps(pivot):
    rel = make_relationship(with_timestamps=True)
    chain = pivot.on.return_value.table.return_value.without_global_scopes.return_value

    current = MagicMock()
    current.id = 1
    current.get_builder.return_value.connection = "sqlite"
    related = MagicMock()
    related.id = 9

    rel.attach(current, related)

    data = chain.create.call_args.args[0]
    assert "created_at" in data and "updated_at" in data


@patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot")
def test_detach_deletes_pivot_record(pivot):
    rel = make_relationship()
    chain = pivot.on.return_value.table.return_value.without_global_scopes.return_value.where.return_value

    current = MagicMock()
    current.id = 1
    current.get_builder.return_value.connection = "sqlite"
    related = MagicMock()
    related.id = 9

    rel.detach(current, related)

    chain.delete.assert_called_once()


@patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot")
def test_attach_related_creates_pivot_record(pivot):
    rel = make_relationship()
    chain = pivot.table.return_value.on.return_value.without_global_scopes.return_value

    current = MagicMock()
    current.id = 2
    current.get_builder.return_value.connection_name = "sqlite"
    related = MagicMock()
    related.id = 7

    rel.attach_related(current, related)

    chain.create.assert_called_once_with({"store_id": 2, "product_id": 7})


@patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot")
def test_detach_related_deletes_pivot_record(pivot):
    rel = make_relationship()
    chain = pivot.on.return_value.table.return_value.without_global_scopes.return_value.where.return_value

    current = MagicMock()
    current.id = 2
    current.get_builder.return_value.connection_name = "sqlite"
    related = MagicMock()
    related.id = 7

    rel.detach_related(current, related)

    chain.delete.assert_called_once()


def test_relate_builds_query_with_joins_and_where():
    rel = make_relationship()
    query = make_builder(table_name="products")
    rel.get_builder = MagicMock(return_value=query)

    owner_builder = make_builder(table_name="stores")

    class Related:
        id = 3

        def get_builder(self_inner):
            return owner_builder

    result = rel.relate(Related())

    assert query.join.call_count == 2
    assert result is query


async def test_make_query_for_single_relation():
    rel = make_relationship()
    fetched = []
    query_builder = make_builder(table_name="products", get_result=fetched)
    rel.get_builder = MagicMock(return_value=query_builder)

    owner_query = make_builder(table_name="stores")

    class Relation:
        id = 4

    out = await rel.make_query(owner_query, Relation())

    assert out is fetched
    query_builder.get.assert_awaited_once()


async def test_get_related_hydrates_pivot(monkeypatch):
    rel = make_relationship(with_timestamps=True)
    model = make_pivot_model()
    fetched = [model]

    query_builder = make_builder(table_name="products", get_result=fetched)
    rel.get_builder = MagicMock(return_value=query_builder)

    with patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot"):
        owner_query = make_builder(table_name="stores")

        class Relation:
            id = 4

        out = await rel.get_related(owner_query, Relation())

    assert out is fetched
    model.__original_attributes__.update.assert_called_once()


async def test_make_query_infers_pivot_table_and_keys():
    rel = BelongsToMany("Product", local_owner_key="id", other_owner_key="id")
    rel.local_key = None
    rel.foreign_key = None

    query_builder = make_builder(table_name="products", get_result=[])
    rel.get_builder = MagicMock(return_value=query_builder)
    owner_query = make_builder(table_name="stores")

    await rel.make_query(owner_query, Collection([]))

    assert rel._table == "product_store"
    assert rel.foreign_key == "product_id"
    assert rel.local_key == "store_id"


async def test_apply_query_hydrates_with_timestamps_and_fields():
    rel = make_relationship(with_timestamps=True, with_fields=["extra"])
    model = make_pivot_model(extra="x")
    fetched = [model]

    query = make_builder(table_name="products", get_result=fetched)
    owner = MagicMock()
    owner.get_table_name.return_value = "stores"
    owner.id = 5

    with patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot"):
        out = await rel.apply_query(query, owner)

    assert out is fetched
    model.__original_attributes__.update.assert_called_once()
    model.delete_attribute.assert_any_call("m_reserved2")


async def test_apply_query_infers_pivot_table_when_missing():
    rel = BelongsToMany("Product", local_owner_key="id", other_owner_key="id")
    rel.local_key = None
    rel.foreign_key = None

    query = make_builder(table_name="products", get_result=[])
    owner = MagicMock()
    owner.get_table_name.return_value = "stores"

    with patch("fastapi_startkit.masoniteorm.relationships.BelongsToMany.Pivot"):
        await rel.apply_query(query, owner)

    assert rel._table == "product_store"

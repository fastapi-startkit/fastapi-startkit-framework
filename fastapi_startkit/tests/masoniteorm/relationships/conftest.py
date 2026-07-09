"""Shared test doubles for the relationship unit tests.

``make_builder`` returns a chainable mock standing in for masoniteorm's async
``QueryBuilder``. The relationship classes are unit-tested against this mock
rather than real sqlite because they are not currently wired to the fork's async
``QueryBuilder``:

* the builder (``masoniteorm/models/builder.py``) lacks ``table()``,
  ``without_global_scopes()`` and ``add_select()``, all called by
  ``BelongsToMany``;
* ``BaseRelationship.get_builder()`` calls ``self.fn()`` with no args against
  ``BelongsToMany``'s ``lambda x:`` factory, raising ``TypeError``;
* ``attach``/``detach`` chain those same missing methods on a plain ``Pivot``
  model.

The ``CHAINABLE`` list below mirrors exactly the builder methods the relationship
code expects, so the relationship logic can be tested in isolation. Real-DB
wiring is tracked in the project backlog.
"""

from unittest.mock import AsyncMock, MagicMock


CHAINABLE = [
    "select",
    "add_select",
    "join",
    "table",
    "where",
    "where_in",
    "where_column",
    "run_scopes",
    "without_global_scopes",
    "when",
    "new",
    "with_",
]


def make_builder(table_name="others", get_result=None, columns=None, connection="sqlite"):
    """A chainable query-builder mock.

    Every query-shaping method returns the same mock so call chains resolve,
    while ``get`` is awaitable and ``get_table_name`` is fixed.
    """
    builder = MagicMock(name=f"builder<{table_name}>")
    builder.get_table_name.return_value = table_name
    builder._columns = columns
    builder.connection = connection
    builder.connection_name = connection
    for method in CHAINABLE:
        getattr(builder, method).return_value = builder
    builder.get = AsyncMock(return_value=[] if get_result is None else get_result)
    return builder

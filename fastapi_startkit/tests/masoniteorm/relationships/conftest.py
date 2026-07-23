"""Test doubles for the ``BaseRelationship`` contract unit tests.

``make_builder`` returns a chainable mock standing in for masoniteorm's async
``QueryBuilder``. These tests target ``BaseRelationship``'s descriptor and key
handling directly, so the builder is faked: only the join-clause and
``__getattr__`` delegation tests touch it, and both assert on how
``BaseRelationship`` drives the builder rather than on real query execution.
Real-DB behaviour of the concrete relationships is covered by the sqlite
integration suites under ``tests/masoniteorm/sqlite/relationships``.
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

import inspect
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar, overload

from fastapi_startkit.masoniteorm.expressions.expressions import (
    JoinClause,
    QueryExpression,
    SelectExpression,
    UpdateQueryExpression,
    SubSelectExpression,
    SubGroupExpression,
    OrderByExpression,
    GroupByExpression,
    HavingExpression,
    AggregateExpression,
    BetweenExpression,
)
from fastapi_startkit.masoniteorm.query.EagerLoadMixin import EagerLoadMixin
from fastapi_startkit.masoniteorm.query.support import SupportMixin

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.collection import Collection
    from fastapi_startkit.masoniteorm.connections.connection import Connection
    from fastapi_startkit.masoniteorm.models.model import Model

TModel = TypeVar("TModel", bound="Model")

# where(lambda q: q.where(...)) — the callable receives a nested builder and
# returns it, which the parent renders as a parenthesised subgroup.
type WhereGroup[M: "Model"] = Callable[["QueryBuilder[M]"], "QueryBuilder[M]"]

# select_sub()/add_select() subquery source: a builder, or a callable that
# receives a fresh builder and returns the subquery.
type Subquery = "QueryBuilder[Any] | Callable[[QueryBuilder[Any]], QueryBuilder[Any]]"
type SelectEntry = "str | dict[str, str | Subquery]"


class QueryBuilder(EagerLoadMixin, SupportMixin, Generic[TModel]):
    operators = [
        "=",
        "<",
        ">",
        "<=",
        ">=",
        "<>",
        "!=",
        "<=>",
        "like",
        "like binary",
        "not like",
        "ilike",
        "&",
        "|",
        "^",
        "<<",
        ">>",
        "&~",
        "is",
        "is not",
        "rlike",
        "not rlike",
        "regexp",
        "not regexp",
        "~",
        "~*",
        "!~",
        "!~*",
        "similar to",
        "not similar to",
        "not ilike",
        "~~*",
        "!~~*",
    ]

    def __init__(self, connection: "Connection", grammar: Any, processor: Any):
        super().__init__()
        self.connection = connection
        self.grammar = grammar
        self.processor = processor

        self._columns: list[Any] = []
        self._table = ""
        self._limit = False
        self._offset = False
        self._wheres = []
        self._joins = ()
        self._aggregates = ()
        self._order_by = ()
        self._group_by = ()
        self._having = ()
        self._distinct = False

        self._sql = ""
        self._bindings = ()

        self._global_scopes = {}
        self._action = "select"

    def set_action(self, action: str) -> "Self":
        self._action = action
        return self

    def set_model(self, model: "TModel") -> "Self":
        self._model = model
        self._table = model.get_table_name()
        self._global_scopes = model._global_scopes
        return self

    def with_(self, *eagers) -> "Self":
        self._eager_relation.register(eagers)
        return self

    def get_table_name(self) -> str:
        return self._table

    def table(self, table: str) -> "Self":
        self._table = table
        return self

    def where_in(self, column: str, values: Iterable[Any]) -> "Self":
        if hasattr(values, "_items"):
            values = getattr(values, "_items")
        values = list(values) if not isinstance(values, list) else values
        self._wheres.append(QueryExpression(column, "IN", values))
        return self

    def select(self, *args: "str | list[str]") -> "Self":
        for arg in args:
            if isinstance(arg, list):
                for column in arg:
                    self._columns += (SelectExpression(column),)
            else:
                for column in arg.split(","):
                    self._columns += (SelectExpression(column),)
        return self

    def select_sub(self, subquery: "Subquery", alias: str) -> "Self":
        """Add ``(subquery) AS alias`` to the selection.

        ``subquery`` is a builder, or a callable that receives a fresh table-less
        builder and returns one.
        """
        if not isinstance(subquery, QueryBuilder) and callable(subquery):
            subquery = subquery(QueryBuilder(self.connection, self.grammar, self.processor))
        if not isinstance(subquery, QueryBuilder):
            raise TypeError("select_sub() expects a QueryBuilder subquery or a callable returning one.")
        self._columns.append(SubGroupExpression(subquery, alias))
        return self

    def add_select(self, *columns: "SelectEntry | list[SelectEntry]") -> "Self":
        """Append columns to the current selection without replacing it.

        Plain string columns are appended once. A ``{alias: subquery}`` entry
        adds a correlated column via :meth:`select_sub`, first selecting
        ``{table}.*`` when nothing is selected yet so the base columns survive.
        A string value under a string key is still a plain column.
        """
        entries: list[SelectEntry] = []
        for column in columns:
            if isinstance(column, list):
                entries.extend(column)
            else:
                entries.append(column)

        for entry in entries:
            pairs: Iterable[tuple[str | None, str | Subquery]] = (
                entry.items() if isinstance(entry, dict) else [(None, entry)]
            )
            for alias, value in pairs:
                if isinstance(value, str):
                    if not self._is_selected(value):
                        self._columns.append(SelectExpression(value))
                    continue
                if alias is None:
                    raise TypeError(
                        "add_select() received a subquery without a string alias; "
                        "pass {alias: subquery} or use select_sub(subquery, alias)."
                    )
                if not self._columns:
                    self.select(f"{self._table}.*")
                self.select_sub(value, alias)
        return self

    def _is_selected(self, column: str) -> bool:
        return any(
            isinstance(existing, SelectExpression) and existing.alias is None and existing.column == column
            for existing in self._columns
        )

    def limit(self, limit: int) -> "Self":
        self._limit = limit
        return self

    async def find(self, primary_key: str | int, columns: "list[str] | str | None" = None) -> "TModel | None":
        return await self.where(self._model.__primary_key__, primary_key).first(columns)

    async def find_or_fail(self, primary_key: str | int, columns: "list[str] | str | None" = None) -> "TModel":
        """Return the record matching ``primary_key``.

        Raises:
            ModelNotFoundException: If no record matches ``primary_key``.
        """
        from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException

        result = await self.find(primary_key, columns)
        if result is None:
            raise ModelNotFoundException(f"{type(self._model).__name__} with primary key {primary_key!r} not found.")
        return result

    async def first_or_fail(self, columns: "list[str] | str | None" = None) -> "TModel":
        from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException

        result = await self.first(columns)
        if result is None:
            raise ModelNotFoundException(f"{type(self._model).__name__} not found.")
        return result

    async def first(self, columns: "list[str] | str | None" = None) -> "TModel | None":
        if not columns:
            columns = []

        results = await self.select(columns).limit(1).get()
        return results.first()

    async def get(self, columns: "list[str] | str | None" = None) -> "Collection[TModel]":
        # TODO: apply scopes
        if not columns:
            columns = []
        return await self.get_models(columns)

    async def get_models(self, columns: "list[str] | str | None" = None) -> "Collection[TModel]":
        if not columns:
            columns = []
        self.select(columns)
        models = await self.connection.select(self.to_qmark(), list(self.get_bindings()))
        collection = self._model.hydrate(models)

        if self._eager_relation.eagers or self._eager_relation.nested_eagers or self._eager_relation.callback_eagers:
            await self._load_eagers(collection, self._model)

        return collection

    def get_bindings(self) -> tuple[Any, ...]:
        return self._bindings

    def run_scopes(self) -> "Self":
        for name, scope in self._global_scopes.get(self._action, {}).items():
            scope(self)
        return self

    def without_global_scopes(self) -> "Self":
        self._global_scopes = {}
        return self

    def get_grammar(self):
        return self.grammar(
            columns=self._columns,
            table=self._table,
            limit=self._limit,
            offset=self._offset,
            wheres=self._wheres,
            joins=self._joins,
            aggregates=self._aggregates,
            order_by=self._order_by,
            group_by=self._group_by,
            having=self._having,
            distinct=self._distinct,
        )

    def to_qmark(self) -> str:
        self.run_scopes()
        grammar = self.get_grammar()
        sql = grammar.compile(self._action, qmark=True).to_sql()
        self._bindings = grammar._bindings
        return sql

    def to_sql(self) -> str:
        self.run_scopes()
        return self.get_grammar().compile(self._action).to_sql()

    def offset(self, offset: int) -> "Self":
        self._offset = offset
        return self

    def order_by(self, column: "str | QueryBuilder[Any]", direction: str = "asc") -> "Self":
        direction = direction.upper()
        if isinstance(column, QueryBuilder):
            self._order_by += (OrderByExpression(None, direction, builder=column),)
            return self
        for col in column.split(","):
            col = col.strip()
            self._order_by += (OrderByExpression(col, direction),)
        return self

    def order_by_raw(self, expression: str) -> "Self":
        self._order_by += (OrderByExpression(expression, raw=True),)
        return self

    def latest(self, column: str = "created_at") -> "Self":
        return self.order_by(column, "desc")

    def oldest(self, column: str = "created_at") -> "Self":
        return self.order_by(column, "asc")

    def group_by(self, column: str) -> "Self":
        for col in column.split(","):
            col = col.strip()
            self._group_by += (GroupByExpression(col),)
        return self

    def group_by_raw(self, expression: str) -> "Self":
        self._group_by += (GroupByExpression(expression, raw=True),)
        return self

    def having(self, column: str, equality: str, value: Any) -> "Self":
        self._having += (HavingExpression(column, equality, value),)
        return self

    def where_null(self, column: str) -> "Self":
        self._wheres += (QueryExpression(column, "=", None, "NULL"),)
        return self

    def where_not_null(self, column: str) -> "Self":
        self._wheres += (QueryExpression(column, "=", None, "NOT NULL"),)
        return self

    def or_where_null(self, column: str) -> "Self":
        self._wheres += (QueryExpression(column, "=", None, "NULL", keyword="or"),)
        return self

    def or_where_not_null(self, column: str) -> "Self":
        self._wheres += (QueryExpression(column, "=", None, "NOT NULL", keyword="or"),)
        return self

    def where_not_in(self, column: str, values: Iterable[Any]) -> "Self":
        values = list(values) if not isinstance(values, list) else values
        self._wheres.append(QueryExpression(column, "NOT IN", values))
        return self

    def between(self, column: str, low: Any, high: Any) -> "Self":
        self._wheres += (BetweenExpression(column, low, high, "BETWEEN"),)
        return self

    def not_between(self, column: str, low: Any, high: Any) -> "Self":
        self._wheres += (BetweenExpression(column, low, high, "NOT BETWEEN"),)
        return self

    def left_join(self, table: str, column1: str, equality: str, column2: str) -> "Self":
        return self.join(table, column1, equality, column2, clause="left")

    def right_join(self, table: str, column1: str, equality: str, column2: str) -> "Self":
        # SQLite doesn't support RIGHT JOIN — use left join as fallback
        return self.join(table, column1, equality, column2, clause="right")

    def distinct(self) -> "Self":
        self._distinct = True
        return self

    async def aggregate(self, function: str, column: str):
        self._aggregates += (AggregateExpression(function, column),)
        row = await self.connection.select_one(self.to_qmark(), list(self.get_bindings()))
        if row is None:
            return None
        return next(iter(row.values()))

    async def count(self, column: str = "*"):
        return await self.aggregate("COUNT", column)

    async def exists(self) -> bool:
        """Return True if any record matches the current query, False otherwise."""
        return (await self.count() or 0) > 0

    async def sum(self, column: str):
        return await self.aggregate("SUM", column)

    async def max(self, column: str):
        return await self.aggregate("MAX", column)

    async def min(self, column: str):
        return await self.aggregate("MIN", column)

    async def avg(self, column: str):
        return await self.aggregate("AVG", column)

    async def delete(self, column: str | None = None, value: Any = None):
        if column is not None:
            self.where(column, value)
        self.set_action("delete")
        sql = self.to_qmark()
        return await self.connection.delete(sql, list(self.get_bindings()))

    async def create(self, attributes: dict[str, Any]) -> "TModel":
        model = self._model.new_model_instance(attributes)
        await model.save()

        return model

    async def first_or_create(self, search: dict[str, Any], attributes: dict[str, Any] | None = None) -> "TModel":
        instance = await self.where(search).first()
        if instance is not None:
            return instance

        return await self.create({**(attributes or {}), **search})

    async def update_or_create(self, search: dict[str, Any], attributes: dict[str, Any] | None = None) -> "TModel":
        instance = await self.where(search).first()
        if instance is not None:
            if attributes:
                await instance.update(attributes)
            return instance

        return await self.create({**(attributes or {}), **search})

    async def insert(self, values: dict[str, Any] | list[dict[str, Any]]) -> int | None:
        self.set_action("bulk_create")

        if not values:
            return None

        # Single record → treat as a one-item batch
        if isinstance(values, dict):
            values = [values]
        else:
            values = [{k: row[k] for k in sorted(row)} for row in values]

        self._columns = values

        sql = self.to_qmark()
        bindings = [val for row in values for val in row.values()]
        return await self.connection.insert(sql, bindings)

    async def insert_get_id(
        self,
        values: dict[str, Any] | list[dict[str, Any]],
        sequences: str | None = None,
    ) -> int | None:
        sql = self.grammar().compile_insert_get_id(self, values, sequences)
        bindings = self.clean_bindings(values)

        return await self.connection.insert_get_id(sql, bindings)

    async def update(self, values: dict[str, Any]) -> int:
        updates = [UpdateQueryExpression(col, val) for col, val in values.items()]
        grammar = self.grammar()
        sql = grammar._compile_update(query=self, values=updates, qmark=True).to_sql()
        bindings = list(grammar._bindings)
        return await self.connection.update(sql, bindings)

    async def paginate(self, per_page: int = 15, page: int = 1):
        from fastapi_startkit.masoniteorm.pagination import LengthAwarePaginator

        # Build a count query using a fresh builder with the same wheres/table/model
        count_builder = self.connection.query().set_model(self._model)
        count_builder._wheres = list(self._wheres)
        count_builder._joins = self._joins
        count_builder._global_scopes = self._global_scopes
        total = await count_builder.count() or 0

        offset = (page - 1) * per_page
        results = await self.limit(per_page).offset(offset).get()
        return LengthAwarePaginator(results, per_page, page, int(total))

    async def simple_paginate(self, per_page: int = 15, page: int = 1):
        from fastapi_startkit.masoniteorm.pagination import SimplePaginator

        offset = (page - 1) * per_page
        # Fetch one extra record to detect if there is a next page
        results = await self.limit(per_page + 1).offset(offset).get()
        return SimplePaginator(results, per_page, page)

    async def chunk(self, count: int):
        """Yield results in batches of ``count`` using offset/limit paging.

        Mirrors Laravel's ``chunk()``: iteration stops as soon as a batch
        comes back empty or shorter than ``count``, so it never loops forever.
        """
        if count <= 0:
            raise ValueError("chunk() size must be a positive integer.")

        page = 0
        while True:
            results = await self.limit(count).offset(page * count).get()
            if len(results) == 0:
                break

            yield results

            if len(results) < count:
                break
            page += 1

    async def chunk_by_id(
        self, count: int, column: str | None = None, alias: str | None = None, descending: bool = False
    ):
        if count <= 0:
            raise ValueError("chunk_by_id() size must be a positive integer.")

        column = column or self._model.__primary_key__
        alias = alias or column
        operator = "<" if descending else ">"
        direction = "desc" if descending else "asc"

        base_wheres = list(self._wheres)
        offset = self._offset or 0
        remaining = self._limit if self._limit is not False else None

        last_id = None
        page = 1
        while True:
            limit = count if remaining is None else min(count, remaining)
            if limit == 0:
                break

            self._wheres = list(base_wheres)
            self._order_by = ()
            # The starting offset only applies to the first page; keyset
            # filtering drives every page after that.
            self._offset = offset if page == 1 else False
            if last_id is not None:
                self.where(column, operator, last_id)

            results = await self.order_by(column, direction).limit(limit).get()
            count_results = len(results)
            if count_results == 0:
                break

            if remaining is not None:
                remaining = max(remaining - count_results, 0)

            yield results

            # count_results != 0 above guarantees a last row.
            last_id = results[-1].get_attributes().get(alias)
            if last_id is None:
                raise RuntimeError(
                    f"The chunk_by_id operation was aborted because the [{alias}] "
                    "column is not present in the query result."
                )

            if count_results != count:
                break
            page += 1

    async def chunk_by_id_desc(self, count: int, column: str | None = None, alias: str | None = None):
        async for results in self.chunk_by_id(count, column, alias, descending=True):
            yield results

    def new(self):
        # Carry the current table so a nested builder (e.g. a where(lambda ...)
        # subgroup) prefixes its columns correctly instead of rendering a
        # table-less ."column". Callers that want a different table override it
        # with .table(...) as usual.
        return self.connection.query().table(self._table)

    def invalid_operator(self, operator: Any) -> bool:
        """Determine whether an operator is not supported by the builder."""
        return not isinstance(operator, str) or operator.lower() not in self.operators

    @overload
    def where(self, column: str, /) -> "Self": ...

    @overload
    def where(self, column: str, value: Any, /) -> "Self": ...

    @overload
    def where(self, column: str, operator: str, value: Any, /) -> "Self": ...

    @overload
    def where(self, column: dict[str, Any], /) -> "Self": ...

    @overload
    def where(self, column: "WhereGroup[TModel]", /) -> "Self": ...

    def where(self, column: "str | dict[str, Any] | WhereGroup[TModel]", *args: Any) -> "Self":
        """Specifies a where expression.

        Arguments:
            column {string | dict | callable} -- The column to search, a dict of
                column/value pairs, or a callable receiving a nested builder.

        Keyword Arguments:
            args {List} -- The operator and the value of the column to search. (default: {None})

        Returns:
            self
        """
        operator, value = self._extract_operator_value(*args)

        if inspect.isfunction(column):
            builder = column(self.new())
            self._wheres += ((QueryExpression(None, operator, SubGroupExpression(builder))),)
        elif isinstance(column, dict):
            for key, value in column.items():
                self._wheres += ((QueryExpression(key, "=", value, "value")),)
        elif isinstance(value, QueryBuilder):
            self._wheres += ((QueryExpression(column, operator, SubSelectExpression(value))),)
        else:
            self._wheres += ((QueryExpression(column, operator, value, "value")),)
        return self

    def or_where(self, column: str, *args: Any) -> "Self":
        operator, value = self._extract_operator_value(*args)
        self._wheres += ((QueryExpression(column, operator, value, "value", keyword="or")),)
        return self

    def where_raw(self, expression: str, bindings: tuple[Any, ...] = ()) -> "Self":
        self._wheres += (QueryExpression(expression, "=", None, raw=True, bindings=bindings),)
        return self

    def or_where_raw(self, expression: str, bindings: tuple[Any, ...] = ()) -> "Self":
        self._wheres += (QueryExpression(expression, "=", None, raw=True, keyword="or", bindings=bindings),)
        return self

    def join(self, table: str, column1: str, equality: str, column2: str, clause: str = "join") -> "Self":
        join_clause = JoinClause(table, clause=clause)
        join_clause.on(column1, equality, column2)
        self._joins += (join_clause,)
        return self

    _WHERE_COLUMN_OPERATORS = ("=", "!=", "<>", ">", ">=", "<", "<=")

    def _normalize_where_column(self, operator: str, column2: str | None):
        """Resolve the where_column arity.

        Two-arg ``(col1, col2)`` defaults the operator to ``=``; three-arg
        ``(col1, operator, col2)`` validates the operator.
        """
        if column2 is None:
            return "=", operator
        if operator not in self._WHERE_COLUMN_OPERATORS:
            raise ValueError(
                f"Invalid where_column operator {operator!r}. "
                f"Expected one of: {', '.join(self._WHERE_COLUMN_OPERATORS)}"
            )
        return operator, column2

    def where_column(self, column1: str, operator: str, column2: str | None = None) -> "Self":
        """Compare two columns (identifiers, never bound values), joined with AND."""
        operator, column2 = self._normalize_where_column(operator, column2)
        self._wheres += (QueryExpression(column1, operator, column2, "value_equals"),)
        return self

    def or_where_column(self, column1: str, operator: str, column2: str | None = None) -> "Self":
        """Compare two columns (identifiers, never bound values), joined with OR."""
        operator, column2 = self._normalize_where_column(operator, column2)
        self._wheres += (QueryExpression(column1, operator, column2, "value_equals", keyword="or"),)
        return self

    def when(self, condition: Any, callback: Callable[["Self"], Any]) -> "Self":
        if condition:
            callback(self)
        return self

    def where_exists(self, builder: "QueryBuilder[Any]") -> "Self":
        self._wheres += (QueryExpression(None, "EXISTS", SubSelectExpression(builder)),)
        return self

    def or_where_exists(self, builder: "QueryBuilder[Any]") -> "Self":
        self._wheres += (QueryExpression(None, "EXISTS", SubSelectExpression(builder), keyword="or"),)
        return self

    def where_has(self, relation: str, callback: Callable[..., Any] | None = None) -> "Self":
        related = getattr(self._model.__class__, relation)
        if callback:
            related.query_where_exists(self, callback, method="where_exists")
        else:
            related.query_has(self, method="where_exists")
        return self

    def or_where_has(self, relation: str, callback: Callable[..., Any] | None = None) -> "Self":
        related = getattr(self._model.__class__, relation)
        if callback:
            related.query_where_exists(self, callback, method="or_where_exists")
        else:
            related.query_has(self, method="or_where_exists")
        return self

    @classmethod
    def clean_bindings(cls, values: dict[str, Any] | list[dict[str, Any]]) -> list[Any]:
        if isinstance(values, dict):
            values = [values]
        return [val for row in values for val in row.values()]

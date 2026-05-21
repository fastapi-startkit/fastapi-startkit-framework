import inspect
from typing import TYPE_CHECKING, Any

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
    from fastapi_startkit.masoniteorm.connections.connection import Connection


class QueryBuilder(EagerLoadMixin, SupportMixin):
    def __init__(self, connection: "Connection", grammar, processor):
        super().__init__()
        self.connection = connection
        self.grammar = grammar
        self.processor = processor

        self._columns = []
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

    def set_action(self, action: str) -> "QueryBuilder":
        self._action = action
        return self

    def set_model(self, model) -> "QueryBuilder":
        self._model = model
        self._table = model.get_table_name()
        self._global_scopes = model._global_scopes
        return self

    def with_(self, *eagers) -> "QueryBuilder":
        self._eager_relation.register(eagers)
        return self

    def get_table_name(self) -> str:
        return self._table

    def where_in(self, column: str, values) -> "QueryBuilder":
        if hasattr(values, "_items"):
            values = values._items
        values = list(values) if not isinstance(values, list) else values
        self._wheres.append(QueryExpression(column, "IN", values))
        return self

    def select(self, *args) -> "QueryBuilder":
        for arg in args:
            if isinstance(arg, list):
                for column in arg:
                    self._columns += (SelectExpression(column),)
            else:
                for column in arg.split(","):
                    self._columns += (SelectExpression(column),)
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        self._limit = limit
        return self

    async def find(self, primary_key: str | int, columns=None):
        return await self.where(self._model.__primary_key__, primary_key).first(columns)

    async def find_or_fail(self, primary_key: str | int, columns=None):
        from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException

        result = await self.find(primary_key, columns)
        if result is None:
            raise ModelNotFoundException(
                f"{self._model.__class__.__name__} with primary key {primary_key!r} not found."
            )
        return result

    async def first_or_fail(self, columns=None):
        from fastapi_startkit.masoniteorm.exceptions import ModelNotFoundException

        result = await self.first(columns)
        if result is None:
            raise ModelNotFoundException(
                f"{self._model.__name__} not found."
            )
        return result

    async def first(self, columns=None):
        if not columns:
            columns = []

        results = await self.select(columns).limit(1).get()
        return results.first()

    async def get(self, columns=None):
        # TODO: apply scopes
        if not columns:
            columns = []
        return await self.get_models(columns)

    async def get_models(self, columns=None):
        self.select(columns)
        models = await self.connection.select(self.to_qmark(), self.get_bindings())
        collection = self._model.hydrate(models)

        if self._eager_relation.eagers or self._eager_relation.nested_eagers or self._eager_relation.callback_eagers:
            await self._load_eagers(collection, self._model)

        return collection

    def get_bindings(self) -> tuple:
        return self._bindings

    def run_scopes(self) -> "QueryBuilder":
        for name, scope in self._global_scopes.get(self._action, {}).items():
            scope(self)
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

    def offset(self, offset: int) -> "QueryBuilder":
        self._offset = offset
        return self

    def order_by(self, column: str, direction: str = "asc") -> "QueryBuilder":
        direction = direction.upper()
        for col in column.split(","):
            col = col.strip()
            self._order_by += (OrderByExpression(col, direction),)
        return self

    def order_by_raw(self, expression: str) -> "QueryBuilder":
        self._order_by += (OrderByExpression(expression, raw=True),)
        return self

    def latest(self, column: str = "created_at") -> "QueryBuilder":
        return self.order_by(column, "desc")

    def oldest(self, column: str = "created_at") -> "QueryBuilder":
        return self.order_by(column, "asc")

    def group_by(self, column: str) -> "QueryBuilder":
        for col in column.split(","):
            col = col.strip()
            self._group_by += (GroupByExpression(col),)
        return self

    def group_by_raw(self, expression: str) -> "QueryBuilder":
        self._group_by += (GroupByExpression(expression, raw=True),)
        return self

    def having(self, column: str, equality: str, value) -> "QueryBuilder":
        self._having += (HavingExpression(column, equality, value),)
        return self

    def where_null(self, column: str) -> "QueryBuilder":
        self._wheres += (QueryExpression(column, "=", None, "NULL"),)
        return self

    def where_not_null(self, column: str) -> "QueryBuilder":
        self._wheres += (QueryExpression(column, "=", None, "NOT NULL"),)
        return self

    def where_not_in(self, column: str, values) -> "QueryBuilder":
        values = list(values) if not isinstance(values, list) else values
        self._wheres.append(QueryExpression(column, "NOT IN", values))
        return self

    def between(self, column: str, low, high) -> "QueryBuilder":
        self._wheres += (BetweenExpression(column, low, high, "BETWEEN"),)
        return self

    def not_between(self, column: str, low, high) -> "QueryBuilder":
        self._wheres += (BetweenExpression(column, low, high, "NOT BETWEEN"),)
        return self

    def left_join(self, table: str, column1: str, equality: str, column2: str) -> "QueryBuilder":
        return self.join(table, column1, equality, column2, clause="left")

    def right_join(self, table: str, column1: str, equality: str, column2: str) -> "QueryBuilder":
        # SQLite doesn't support RIGHT JOIN — use left join as fallback
        return self.join(table, column1, equality, column2, clause="right")

    def distinct(self) -> "QueryBuilder":
        self._distinct = True
        return self

    async def aggregate(self, function: str, column: str):
        self._aggregates += (AggregateExpression(function, column),)
        row = await self.connection.select_one(self.to_qmark(), self.get_bindings())
        if row is None:
            return None
        return next(iter(row.values()))

    async def count(self, column: str = "*"):
        return await self.aggregate("COUNT", column)

    async def sum(self, column: str):
        return await self.aggregate("SUM", column)

    async def max(self, column: str):
        return await self.aggregate("MAX", column)

    async def min(self, column: str):
        return await self.aggregate("MIN", column)

    async def avg(self, column: str):
        return await self.aggregate("AVG", column)

    async def delete(self, column=None, value=None):
        if column is not None:
            self.where(column, value)
        self.set_action("delete")
        sql = self.to_qmark()
        return await self.connection.delete(sql, self.get_bindings())

    async def create(self, attributes: dict):
        model = self._model.new_model_instance(attributes)
        await model.save()

        return model

    async def first_or_create(self, search: dict, attributes: dict | None = None):
        instance = await self.where(search).first()
        if instance is not None:
            return instance

        return await self.create({**(attributes or {}), **search})

    async def update_or_create(self, search: dict, attributes: dict | None = None):
        instance = await self.where(search).first()
        if instance is not None:
            if attributes:
                await instance.update(attributes)
            return instance

        return await self.create({**(attributes or {}), **search})

    async def insert(self, values: dict | list) -> int | None:
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

    async def update(self, values: dict) -> int:
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

    def new(self):
        return self.connection.query()

    def where(self, column, *args):
        """Specifies a where expression.

        Arguments:
            column {string} -- The name of the column to search

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

    def or_where(self, column, *args) -> "QueryBuilder":
        operator, value = self._extract_operator_value(*args)
        self._wheres += ((QueryExpression(column, operator, value, "value", keyword="or")),)
        return self

    def join(self, table: str, column1: str, equality: str, column2: str, clause: str = "join") -> "QueryBuilder":
        join_clause = JoinClause(table, clause=clause)
        join_clause.on(column1, equality, column2)
        self._joins += (join_clause,)
        return self

    def where_column(self, column1: str, column2: str) -> "QueryBuilder":
        self._wheres += (QueryExpression(column1, "=", column2, "value_equals"),)
        return self

    def when(self, condition, callback) -> "QueryBuilder":
        if condition:
            callback(self)
        return self

    def where_exists(self, builder: "QueryBuilder") -> "QueryBuilder":
        self._wheres += (QueryExpression(None, "EXISTS", SubSelectExpression(builder)),)
        return self

    def or_where_exists(self, builder: "QueryBuilder") -> "QueryBuilder":
        self._wheres += (QueryExpression(None, "EXISTS", SubSelectExpression(builder), keyword="or"),)
        return self

    def where_has(self, relation: str, callback=None) -> "QueryBuilder":
        related = getattr(self._model.__class__, relation)
        if callback:
            related.query_where_exists(self, callback, method="where_exists")
        else:
            related.query_has(self, method="where_exists")
        return self

    def or_where_has(self, relation: str, callback=None) -> "QueryBuilder":
        related = getattr(self._model.__class__, relation)
        if callback:
            related.query_where_exists(self, callback, method="or_where_exists")
        else:
            related.query_has(self, method="or_where_exists")
        return self

    @classmethod
    def clean_bindings(cls, values):
        if isinstance(values, dict):
            values = [values]
        return [val for row in values for val in row.values()]

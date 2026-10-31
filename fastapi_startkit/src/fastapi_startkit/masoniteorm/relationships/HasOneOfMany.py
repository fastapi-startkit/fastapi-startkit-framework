from typing import TYPE_CHECKING, Literal

from .BaseRelationship import TModel
from .HasOne import HasOne

if TYPE_CHECKING:
    from .HasMany import HasMany

type OfManyAggregate = Literal["max", "min"]

AGGREGATE_DIRECTIONS: dict[str, str] = {"max": "desc", "min": "asc"}


class HasOneOfMany(HasOne[TModel]):
    def __init__(self, relation: "HasMany[TModel]", column: str | None, aggregate: OfManyAggregate):
        if aggregate not in AGGREGATE_DIRECTIONS:
            raise ValueError(f"of_many() aggregate must be one of {', '.join(AGGREGATE_DIRECTIONS)}, got {aggregate!r}")
        if relation.foreign_key is None and relation.attribute is None:
            raise TypeError("of_many() needs a HasMany declared on a model or given an explicit foreign_key")

        relation.set_keys(None, relation.attribute)
        super().__init__(foreign_key=relation.foreign_key, local_key=relation.local_key)
        self.relation = relation
        self.column = column
        self.direction = AGGREGATE_DIRECTIONS[aggregate]
        self.attribute = None

    def model_reference(self) -> str | type:
        return self.relation.model_reference()

    def set_keys(self, owner, attribute):
        return self

    def get_builder(self):
        return self.constrain(self.relation.get_builder())

    def get_exists_builder(self, parent):
        query = self.relation.get_builder()
        return self.constrain(query.table(query.get_table_name(), self.exists_alias(query, parent)))

    def constrain(self, builder):
        table = builder.get_table_name()
        return builder.where(f"{table}.{builder._model.__primary_key__}", "=", self.one_of_many(table))

    def one_of_many(self, table):
        builder = self.relation.get_builder()
        alias = f"{builder.get_table_name()}_of_many"
        key = builder._model.__primary_key__
        column = self.column or key
        query = builder.table(builder.get_table_name(), alias).select(f"{alias}.{key}")
        query.where_column(f"{alias}.{self.foreign_key}", f"{table}.{self.foreign_key}")
        if column != key:
            query.where_not_null(f"{alias}.{column}").order_by(f"{alias}.{column}", self.direction)
        return query.order_by(f"{alias}.{key}", self.direction).limit(1)

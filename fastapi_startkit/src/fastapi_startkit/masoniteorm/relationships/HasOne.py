from ..collection import Collection
from .BaseRelationship import BaseRelationship
from fastapi_startkit.masoniteorm.models import registry


class HasOne(BaseRelationship):
    """Has One Relationship Class."""

    def __init__(self, fn: str, foreign_key=None, local_key=None):
        self.fn = lambda: registry.Registry.resolve(fn)

        self.local_key = local_key or "id"
        self.foreign_key = foreign_key

    def set_keys(self, owner, attribute):
        self.local_key = self.local_key or "id"
        self.foreign_key = self.foreign_key or f"{attribute}_id"

        return self

    def apply_query(self, foreign, owner):
        return foreign.where(self.foreign_key, owner.__attributes__[self.local_key]).first()

    async def get_related(self, query, relation, eagers=(), callback=None):
        builder = self.get_builder().with_(eagers)

        if callback:
            callback(builder)

        if isinstance(relation, Collection):
            return await builder.where_in(
                f"{builder.get_table_name()}.{self.foreign_key}",
                Collection(relation._get_value(self.local_key)).unique(),
            ).get()

        return await builder.where(
            f"{builder.get_table_name()}.{self.foreign_key}",
            getattr(relation, self.local_key),
        ).first()

    def map_related(self, related_result):
        return related_result

    def query_has(self, current_query_builder, method="where_exists"):
        related_builder = self.get_builder()

        getattr(current_query_builder, method)(
            related_builder.where_column(
                f"{related_builder.get_table_name()}.{self.foreign_key}",
                f"{current_query_builder.get_table_name()}.{self.local_key}",
            )
        )

        return related_builder

    def register_related(self, key, model, collection):
        related = collection.where(self.foreign_key, getattr(model, self.local_key)).first()

        model.add_relation({key: related or None})

    def query_where_exists(self, builder, callback, method="where_exists"):
        query = self.get_builder()
        getattr(builder, method)(
            callback(
                query.where_column(
                    f"{query.get_table_name()}.{self.foreign_key}",
                    f"{builder.get_table_name()}.{self.local_key}",
                )
            )
        )
        return query

    async def attach(self, current_model, related_record):
        local_key_value = getattr(current_model, self.local_key)
        if not related_record.is_created():
            related_record.fill({self.foreign_key: local_key_value})
            return await related_record.create(related_record.all_attributes(), cast=True)

        return await related_record.update({self.foreign_key: local_key_value})

    async def detach(self, current_model, related_record):
        return await related_record.update({self.foreign_key: None})

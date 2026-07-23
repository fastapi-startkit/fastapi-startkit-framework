from fastapi_startkit.masoniteorm.models import registry
from .BaseRelationship import BaseRelationship
from ..collection import Collection


class HasManyThrough(BaseRelationship):
    """HasManyThrough Relationship Class."""

    def __init__(
        self,
        fn=list[str],
        local_foreign_key=None,
        other_foreign_key=None,
        local_owner_key=None,
        other_owner_key=None,
    ):
        self.fn = fn

        self.local_key = local_foreign_key
        self.foreign_key = other_foreign_key
        self.local_owner_key = local_owner_key or "id"
        self.other_owner_key = other_owner_key or "id"
        self.distant_builder = None
        self.intermediary_builder = None

    def __set_name__(self, owner, name):
        self.attribute = name

    def get_distance_builder(self):
        """Return a fresh distant builder (never cached — builders are stateful)."""
        model = registry.Registry.resolve(self.fn[0])
        return model().get_builder()

    def get_intermediary_builder(self):
        """Return a fresh intermediary builder (never cached — builders are stateful)."""
        model = registry.Registry.resolve(self.fn[1])
        return model().get_builder()

    def set_keys(self, attribute):
        self.local_key = self.local_key or "id"
        self.foreign_key = self.foreign_key or f"{attribute}_id"
        self.local_owner_key = self.local_owner_key or "id"
        self.other_owner_key = self.other_owner_key or "id"
        return self

    def __get__(self, instance, owner):
        if instance is None or not instance.is_loaded():
            return self

        if instance.relationship_loaded(self.attribute):
            return instance.get_relationship(self.attribute)

        return self.apply_related_query(
            distant_builder=self.get_distance_builder(),
            intermediary_builder=self.get_intermediary_builder(),
            owner=instance,
        )

    def apply_related_query(self, distant_builder, intermediary_builder, owner):
        distant_table = distant_builder.get_table_name()
        intermediate_table = intermediary_builder.get_table_name()

        return (
            distant_builder.select(f"{distant_table}.*, {intermediate_table}.{self.local_key}")
            .join(
                f"{intermediate_table}",
                f"{intermediate_table}.{self.foreign_key}",
                "=",
                f"{distant_table}.{self.other_owner_key}",
            )
            .where(
                f"{intermediate_table}.{self.local_key}",
                getattr(owner, self.local_owner_key),
            )
            .get()
        )

    def relate(self, related_model):
        distant = self.get_distance_builder()
        intermediary = self.get_intermediary_builder()
        return distant.join(
            f"{intermediary.get_table_name()}",
            f"{intermediary.get_table_name()}.{self.foreign_key}",
            "=",
            f"{distant.get_table_name()}.{self.other_owner_key}",
        ).where(
            f"{intermediary.get_table_name()}.{self.local_key}",
            getattr(related_model, self.local_owner_key),
        )

    def get_builder(self):
        return self.get_distance_builder()

    def make_builder(self, eagers=None):
        builder = self.get_builder().with_(eagers)
        return builder

    def register_related(self, key, model, collection):
        related = collection.get(getattr(model, self.local_owner_key), None)
        if related and not isinstance(related, Collection):
            related = Collection(related)

        model.add_relation({key: related if related else None})

    async def get_related(self, current_builder, relation, eagers=None, callback=None):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        distant_table = distant_builder.get_table_name()
        intermediate_table = intermediary_builder.get_table_name()

        if callback:
            callback(current_builder)

        distant_builder.select(f"{distant_table}.*, {intermediate_table}.{self.local_key}").join(
            f"{intermediate_table}",
            f"{intermediate_table}.{self.foreign_key}",
            "=",
            f"{distant_table}.{self.other_owner_key}",
        )

        if isinstance(relation, Collection):
            return await distant_builder.where_in(
                f"{intermediate_table}.{self.local_key}",
                Collection(relation._get_value(self.local_owner_key)).unique(),
            ).get()
        else:
            return await distant_builder.where(
                f"{intermediate_table}.{self.local_key}",
                getattr(relation, self.local_owner_key),
            ).get()

    def query_has(self, current_builder, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        distant_table = distant_builder.get_table_name()
        intermediate_table = intermediary_builder.get_table_name()

        getattr(current_builder, method)(
            distant_builder.join(
                f"{intermediate_table}",
                f"{intermediate_table}.{self.foreign_key}",
                "=",
                f"{distant_table}.{self.other_owner_key}",
            ).where_column(
                f"{intermediate_table}.{self.local_key}",
                f"{current_builder.get_table_name()}.{self.local_owner_key}",
            )
        )

        return distant_builder

    def query_where_exists(self, current_builder, callback, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        distant_table = distant_builder.get_table_name()
        intermediate_table = intermediary_builder.get_table_name()

        getattr(current_builder, method)(
            distant_builder.join(
                f"{intermediate_table}",
                f"{intermediate_table}.{self.foreign_key}",
                "=",
                f"{distant_table}.{self.other_owner_key}",
            )
            .where_column(
                f"{intermediate_table}.{self.local_key}",
                f"{current_builder.get_table_name()}.{self.local_owner_key}",
            )
            .when(callback, lambda q: callback(q))
        )

    def get_with_count_query(self, current_builder, callback):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        distant_table = distant_builder.get_table_name()
        intermediate_table = intermediary_builder.get_table_name()

        if not current_builder._columns:
            current_builder.select("*")

        return_query = current_builder.select_sub(
            lambda q: (
                q.select_count("*")
                .join(
                    f"{intermediate_table}",
                    f"{intermediate_table}.{self.foreign_key}",
                    "=",
                    f"{distant_table}.{self.other_owner_key}",
                )
                .where_column(
                    f"{intermediate_table}.{self.local_key}",
                    f"{current_builder.get_table_name()}.{self.local_owner_key}",
                )
                .table(distant_table)
                .when(
                    callback,
                    lambda q: q.where_in(
                        self.foreign_key,
                        callback(distant_builder.select(self.other_owner_key)),
                    ),
                )
            ),
            f"{self.attribute}_count",
        )

        return return_query

    def map_related(self, related_result):
        return related_result.group_by(self.local_key)

from ..collection import Collection
from .BaseRelationship import BaseRelationship
from fastapi_startkit.masoniteorm.models import registry


class HasOneThrough(BaseRelationship):
    """HasOneThrough Relationship Class."""

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
        self.set_keys(self.attribute)

        if instance is None or not instance.is_loaded():
            return self

        if instance.relationship_loaded(self.attribute):
            return instance.get_relationship(self.attribute)

        return self.apply_relation_query(
            distant_builder=self.get_distance_builder(),
            intermediary_builder=self.get_intermediary_builder(),
            owner=instance,
        )

    def apply_relation_query(self, distant_builder, intermediary_builder, owner):
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        return (
            distant_builder.select(f"{dist_table}.*, {int_table}.{self.local_owner_key} as {self.local_key}")
            .join(
                f"{int_table}",
                f"{int_table}.{self.foreign_key}",
                "=",
                f"{dist_table}.{self.other_owner_key}",
            )
            .where(
                f"{int_table}.{self.local_owner_key}",
                getattr(owner, self.local_key),
            )
            .first()
        )

    def relate(self, related_model):
        distant = self.get_distance_builder()
        intermediary = self.get_intermediary_builder()
        dist_table = distant.get_table_name()
        int_table = intermediary.get_table_name()

        return distant.join(
            f"{int_table}",
            f"{int_table}.{self.foreign_key}",
            "=",
            f"{dist_table}.{self.other_owner_key}",
        ).where_column(
            f"{int_table}.{self.local_owner_key}",
            getattr(related_model, self.local_key),
        )

    def get_builder(self):
        return self.get_distance_builder()

    def make_builder(self, eagers=None):
        builder = self.get_builder().with_(eagers)
        return builder

    def register_related(self, key, model, collection):
        """
        Attach the related model to source models attribute

        Arguments
            key (str): The attribute name
            model (Any): The model instance
            collection (Collection): The data for the related models

        Returns
            None
        """
        related = collection.get(getattr(model, self.local_key), None)
        model.add_relation({key: related[0] if related else None})

    async def get_related(self, current_builder, relation, eagers=None, callback=None):
        """
        Get the data to hydrate the model for the distant table with
        Used when eager loading the model attribute

        Arguments
            query (QueryBuilder): The source models QueryBuilder object
            relation (HasOneThrough): this relationship object
            eagers (Any):
            callback (Any):

        Returns
             dict: the dict to hydrate the distant model with
        """
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        if callback:
            callback(current_builder)

        distant_builder.select(f"{dist_table}.*, {int_table}.{self.local_owner_key} as {self.local_key}").join(
            f"{int_table}",
            f"{int_table}.{self.foreign_key}",
            "=",
            f"{dist_table}.{self.other_owner_key}",
        )

        if isinstance(relation, Collection):
            return await distant_builder.where_in(
                f"{int_table}.{self.local_owner_key}",
                Collection(relation._get_value(self.local_key)).unique(),
            ).get()
        else:
            return await distant_builder.where(
                f"{int_table}.{self.local_owner_key}",
                getattr(relation, self.local_key),
            ).first()

    def query_has(self, current_builder, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        getattr(current_builder, method)(
            distant_builder.join(
                f"{int_table}",
                f"{int_table}.{self.foreign_key}",
                "=",
                f"{dist_table}.{self.other_owner_key}",
            ).where_column(
                f"{int_table}.{self.local_owner_key}",
                f"{current_builder.get_table_name()}.{self.local_key}",
            )
        )

        return distant_builder

    def query_where_exists(self, current_builder, callback, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        getattr(current_builder, method)(
            distant_builder.join(
                f"{int_table}",
                f"{int_table}.{self.foreign_key}",
                "=",
                f"{dist_table}.{self.other_owner_key}",
            )
            .where_column(
                f"{int_table}.{self.local_owner_key}",
                f"{current_builder.get_table_name()}.{self.local_key}",
            )
            .when(callback, lambda q: callback(q))
        )

    def get_with_count_query(self, current_builder, callback):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        if not current_builder._columns:
            current_builder.select("*")

        return_query = current_builder.select_sub(
            lambda q: (
                q.select_count("*")
                .join(
                    f"{int_table}",
                    f"{int_table}.{self.foreign_key}",
                    "=",
                    f"{dist_table}.{self.other_owner_key}",
                )
                .where_column(
                    f"{int_table}.{self.local_owner_key}",
                    f"{current_builder.get_table_name()}.{self.local_key}",
                )
                .table(dist_table)
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

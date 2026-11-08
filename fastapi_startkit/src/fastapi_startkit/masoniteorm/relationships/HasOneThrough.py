from ..collection import Collection
from ..exceptions import LazyLoadingViolation
from .BaseRelationship import BaseRelationship, RelationshipKey, SingleResult, TModel
from fastapi_startkit.masoniteorm.models import registry


class HasOneThrough(BaseRelationship[TModel, SingleResult[TModel]]):
    """HasOneThrough Relationship Class."""

    through_key = "m_through_key"
    local_owner_key: RelationshipKey = RelationshipKey()
    other_owner_key: RelationshipKey = RelationshipKey()

    def __init__(
        self,
        fn: list[str],
        local_foreign_key: str | None = None,
        other_foreign_key: str | None = None,
        local_owner_key: str | None = None,
        other_owner_key: str | None = None,
    ):
        self.fn = fn

        self.local_key = local_foreign_key
        self.foreign_key = other_foreign_key
        self.local_owner_key = local_owner_key
        self.other_owner_key = other_owner_key
        self.distant_builder = None
        self.intermediary_builder = None

    def __set_name__(self, owner, name):
        self.attribute = name
        self.owner_class = owner

    def get_distance_builder(self):
        """Return a fresh distant builder (never cached — builders are stateful)."""
        model = registry.Registry.resolve(self.fn[0])
        return model().get_builder()

    def get_intermediary_builder(self):
        """Return a fresh intermediary builder (never cached — builders are stateful)."""
        model = registry.Registry.resolve(self.fn[1])
        return model().get_builder()

    def default_keys(self):
        owner = self.owner_class
        intermediary = registry.Registry.resolve(self.fn[1])
        return {
            "local_key": owner.__primary_key__,
            "local_owner_key": self.foreign_key_of(owner),
            "foreign_key": intermediary.__primary_key__,
            "other_owner_key": self.foreign_key_of(intermediary),
        }

    def access(self, instance, owner):
        if instance is None or not instance.is_loaded():
            return self

        if instance.relationship_loaded(self.attribute):
            return instance.get_relationship(self.attribute)

        raise LazyLoadingViolation(instance, self.attribute)

    def apply_relation_query(self, distant_builder, intermediary_builder, owner):
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        return (
            distant_builder.select(f"{dist_table}.*, {int_table}.{self.local_owner_key} as {self.through_key}")
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

    def relate(self, related_record):
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
            getattr(related_record, self.local_key),
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

    async def get_related(self, query, relation, eagers=None, callback=None):
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
            callback(query)

        distant_builder.select(f"{dist_table}.*, {int_table}.{self.local_owner_key} as {self.through_key}").join(
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

    def query_has(self, current_query_builder, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        getattr(current_query_builder, method)(
            distant_builder.join(
                f"{int_table}",
                f"{int_table}.{self.foreign_key}",
                "=",
                f"{dist_table}.{self.other_owner_key}",
            ).where_column(
                f"{int_table}.{self.local_owner_key}",
                f"{current_query_builder.get_table_name()}.{self.local_key}",
            )
        )

        return distant_builder

    def query_where_exists(self, builder, callback, method="where_exists"):
        distant_builder = self.get_distance_builder()
        intermediary_builder = self.get_intermediary_builder()
        dist_table = distant_builder.get_table_name()
        int_table = intermediary_builder.get_table_name()

        getattr(builder, method)(
            distant_builder.join(
                f"{int_table}",
                f"{int_table}.{self.foreign_key}",
                "=",
                f"{dist_table}.{self.other_owner_key}",
            )
            .where_column(
                f"{int_table}.{self.local_owner_key}",
                f"{builder.get_table_name()}.{self.local_key}",
            )
            .when(callback, lambda q: callback(q))
        )

    def map_related(self, related_result):
        return related_result.group_by(self.through_key)

from fastapi_startkit.masoniteorm.models import registry
from .BaseRelationship import BaseRelationship
from ..collection import Collection


class MorphMany(BaseRelationship):
    def __init__(self, fn, morph_key="record_type", morph_id="record_id"):
        self.fn = fn
        self.morph_id = morph_id
        self.morph_key = morph_key

    def get_builder(self):
        return self._related_builder

    def set_keys(self, owner, attribute):
        self.morph_id = self.morph_id or "record_id"
        self.morph_key = self.morph_key or "record_type"
        return self

    def __get__(self, instance, owner):
        if instance is None:
            return self

        attribute = self.fn.__name__
        self._related_builder = instance.get_builder()
        self.polymorphic_builder = self.fn(self).query()
        self.set_keys(owner, self.fn)

        if not instance.is_loaded():
            return self

        if attribute in instance._relationships:
            return instance._relationships[attribute]

        return self.apply_query(self._related_builder, instance)

    def __getattr__(self, attribute):
        return getattr(self.fn(self).query(), attribute)

    def apply_query(self, builder, instance):
        """Apply the query and return a dictionary to be hydrated

        Arguments:
            builder {oject} -- The relationship object
            instance {object} -- The current model oject.

        Returns:
            dict -- A dictionary of data which will be hydrated.
        """
        polymorphic_key = self.get_record_key_lookup(instance)
        polymorphic_builder = self.polymorphic_builder
        return (
            polymorphic_builder.where(self.morph_key, polymorphic_key)
            .where(self.morph_id, instance.get_primary_key_value())
            .get()
        )

    def get_related(self, query, relation, eagers=None, callback=None):
        """Gets the relation needed between the relation and the related builder. If the relation is a collection
        then will need to pluck out all the keys from the collection and fetch from the related builder. If
        relation is just a Model then we can just call the model based on the value of the related
        builders primary key.

        Args:
            relation (Model|Collection):

        Returns:
            Model|Collection
        """

        if isinstance(relation, Collection):
            record_type = self.get_record_key_lookup(relation.first())
            if callback:
                return callback(
                    self.polymorphic_builder.where(
                        f"{self.polymorphic_builder.get_table_name()}.{self.morph_key}",
                        record_type,
                    ).where_in(
                        self.morph_id,
                        relation.pluck(relation.first().get_primary_key(), keep_nulls=False).unique(),
                    )
                ).get()
            return (
                self.polymorphic_builder.where(
                    f"{self.polymorphic_builder.get_table_name()}.{self.morph_key}",
                    record_type,
                )
                .where_in(
                    self.morph_id,
                    relation.pluck(relation.first().get_primary_key(), keep_nulls=False).unique(),
                )
                .get()
            )

        else:
            record_type = self.get_record_key_lookup(relation)

            if callback:
                return callback(
                    self.polymorphic_builder.where(self.morph_key, record_type).where(
                        self.morph_id, relation.get_primary_key_value()
                    )
                ).get()
            return (
                self.polymorphic_builder.where(self.morph_key, record_type)
                .where(self.morph_id, relation.get_primary_key_value())
                .get()
            )

    def register_related(self, key, model, collection):
        record_type = self.get_record_key_lookup(model)
        related = collection.where(self.morph_key, record_type).where(self.morph_id, model.get_primary_key_value())

        model.add_relation({key: related})

    def morph_map(self):
        return registry.Registry.get_morph_map()

    def get_record_key_lookup(self, relation):
        morph_name = registry.Registry._reverse_map.get(relation.__class__)
        if morph_name is None:
            raise ValueError(f"Could not find the record type key for the {relation} class")
        return morph_name

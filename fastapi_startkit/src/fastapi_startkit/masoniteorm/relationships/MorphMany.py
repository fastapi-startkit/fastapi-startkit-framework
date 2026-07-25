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

    def _related_model(self):
        """Resolve the related model class from the registry (e.g. ``'Like'`` → ``Like``)."""
        return registry.Registry.resolve(self.fn)

    def _related_query(self):
        return self._related_model().query()

    def __get__(self, instance, owner):
        if instance is None:
            return self

        self._related_builder = instance.get_builder()
        self.polymorphic_builder = self._related_query()
        self.set_keys(owner, self.attribute)

        if not instance.is_loaded():
            return self

        if self.attribute in instance._relationships:
            return instance._relationships[self.attribute]

        return self.apply_query(self._related_builder, instance)

    def __getattr__(self, attribute):
        if attribute.startswith("_"):
            raise AttributeError(attribute)
        builder = self.__dict__.get("_related_builder")
        if builder is None:
            raise AttributeError(attribute)
        return getattr(builder, attribute)

    def apply_query(self, builder, instance):
        polymorphic_key = self.get_record_key_lookup(instance)
        return (
            self.polymorphic_builder.where(self.morph_key, polymorphic_key)
            .where(self.morph_id, instance.get_attribute(instance.__primary_key__))
            .get()
        )

    async def get_related(self, query, relation, eagers=None, callback=None):
        if isinstance(relation, Collection):
            record_type = self.get_record_key_lookup(relation.first())
            builder = (
                self._related_query()
                .where(self.morph_key, record_type)
                .where_in(
                    self.morph_id,
                    relation.pluck(relation.first().__primary_key__, keep_nulls=False).unique(),
                )
            )
        else:
            record_type = self.get_record_key_lookup(relation)
            builder = (
                self._related_query()
                .where(self.morph_key, record_type)
                .where(self.morph_id, relation.get_attribute(relation.__primary_key__))
            )

        if callback:
            builder = callback(builder)

        return await builder.get()

    def register_related(self, key, model, collection):
        record_type = self.get_record_key_lookup(model)
        related = collection.where(self.morph_key, record_type).where(
            self.morph_id, model.get_attribute(model.__primary_key__)
        )
        model.add_relation({key: related})

    def map_related(self, related_result):
        return related_result

    def morph_map(self):
        return registry.Registry.get_morph_map()

    def get_record_key_lookup(self, relation):
        morph_name = registry.Registry._reverse_map.get(relation.__class__)
        if morph_name is None or morph_name == relation.__class__.__name__:
            raise ValueError(f"Could not find the record type key for the {relation} class")
        return morph_name

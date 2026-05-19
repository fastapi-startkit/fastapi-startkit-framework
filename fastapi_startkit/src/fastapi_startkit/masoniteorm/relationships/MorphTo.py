from fastapi_startkit.masoniteorm.models import registry
from .BaseRelationship import BaseRelationship
from ..collection import Collection


class MorphTo(BaseRelationship):
    def __init__(self, fn: str, morph_key="record_type", morph_id="record_id"):
        self.fn = fn
        self.morph_id = morph_id
        self.morph_key = morph_key
        self.attribute = None

    def __set_name__(self, owner, name):
        self.attribute = name

    def get_builder(self):
        return self._related_builder

    def set_keys(self):
        self.morph_id = self.morph_id or "record_id"
        self.morph_key = self.morph_key or "record_type"
        return self

    def __get__(self, instance, owner):
        self.set_keys()

        if instance is None or not instance.is_loaded():
            return self

        self._related_builder = instance.get_builder()

        if instance.relationship_loaded(self.attribute):
            return instance.get_relationship(self.attribute)

        return self.apply_query(self._related_builder, instance)

    def __getattr__(self, attribute):
        relationship = registry.Registry.resolve(self.fn)()
        return getattr(relationship._related_builder, attribute)

    def apply_query(self, builder, instance):
        model = self.morph_map().get(instance.__attributes__[self.morph_key])
        record = instance.__attributes__[self.morph_id]

        return model.where(model.__primary_key__, record).first()

    async def get_related(self, query, relation, eagers=None, callback=None):
        if isinstance(relation, Collection):
            relations = Collection()
            for group, items in relation.group_by(self.morph_key).items():
                morphed_model = self.morph_map().get(group)
                relations.merge(
                    await morphed_model.where_in(
                        f"{morphed_model.__table__}.{morphed_model.__primary_key__}",
                        Collection(items).pluck(self.morph_id, keep_nulls=False).unique(),
                    ).get()
                )
            return relations
        else:
            model = await self.morph_map().get(getattr(relation, self.morph_key))
            if model:
                return await model.find(getattr(relation, self.morph_id))

    def register_related(self, key, model, collection):
        morphed_model = self.morph_map().get(getattr(model, self.morph_key))

        related = collection.where(morphed_model.__primary_key__, getattr(model, self.morph_id)).first()

        model.add_relation({key: related})

    def morph_map(self):
        return registry.Registry.get_morph_map()

    def map_related(self, related_result):
        return related_result

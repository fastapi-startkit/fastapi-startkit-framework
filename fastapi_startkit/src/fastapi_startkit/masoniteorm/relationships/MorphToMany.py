from fastapi_startkit.masoniteorm.models import registry
from .BaseRelationship import BaseRelationship
from ..collection import Collection


class MorphToMany(BaseRelationship):
    def __init__(self, fn, morph_key="record_type", morph_id="record_id"):
        if isinstance(fn, str):
            self.fn = None
            self.morph_key = fn
            self.morph_id = morph_key
        else:
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

        self._related_builder = instance.get_builder()
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
        model = self.morph_map().get(instance.__attributes__[self.morph_key])
        record = instance.__attributes__[self.morph_id]

        return model.where(model.__primary_key__, record).first()

    async def get_related(self, query, relation, eagers=None, callback=None):
        if isinstance(relation, Collection):
            relations = Collection()
            for group, items in relation.group_by(self.morph_key).items():
                morphed_model = self.morph_map().get(group)
                if morphed_model is None:
                    continue
                relations.merge(
                    await morphed_model.where_in(
                        f"{morphed_model.__table__}.{morphed_model.__primary_key__}",
                        Collection(items).pluck(self.morph_id, keep_nulls=False).unique(),
                    ).get()
                )
            return relations

        model = self.morph_map().get(getattr(relation, self.morph_key))
        if model:
            return await model.find(getattr(relation, self.morph_id))
        return None

    def register_related(self, key, model, collection):
        morphed_model = self.morph_map().get(getattr(model, self.morph_key))

        related = collection.where(morphed_model.__primary_key__, getattr(model, self.morph_id))

        model.add_relation({key: related})

    def map_related(self, related_result):
        return related_result

    def morph_map(self):
        return registry.Registry.get_morph_map()

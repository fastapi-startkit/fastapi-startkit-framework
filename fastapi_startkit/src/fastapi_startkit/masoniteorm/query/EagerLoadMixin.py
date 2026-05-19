import inspect

from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.query.EagerRelation import EagerRelations


class EagerLoadMixin:
    def __init__(self):
        self._eager_relation = EagerRelations()

    async def _load_eagers(self, models, model):
        for eager_load in self._eager_relation.get_eagers():
            if isinstance(eager_load, dict):
                # Nested or callback eagers
                for relation, eagers in eager_load.items():
                    callback = None
                    if inspect.isclass(model):
                        related = getattr(model, relation)
                    elif callable(eagers):
                        related = getattr(model, relation)
                        callback = eagers
                    else:
                        related = model.get_related(relation)

                    result_set = await related.get_related(
                        self,
                        models,
                        eagers=eagers,
                        callback=callback,
                    )

                    await self._register_relationships_to_model(
                        related,
                        result_set,
                        models,
                        relation_key=relation,
                    )
            else:
                # Flat eagers
                for eager in eager_load:
                    if inspect.isclass(model):
                        related = getattr(model, eager)
                    else:
                        related = model.get_related(eager)

                    result_set = await related.get_related(self, models)

                    await self._register_relationships_to_model(
                        related,
                        related_result=result_set,
                        models=models,
                        relation_key=eager,
                    )

    async def _register_relationships_to_model(self, related, related_result, models, relation_key):
        if related_result and isinstance(models, Collection):
            map_related = self._map_related(related_result, related)
            for model in models:
                if isinstance(related_result, Collection):
                    related.register_related(relation_key, model, map_related)
                else:
                    model.add_relation({relation_key: map_related or None})
        else:
            models.add_relation({relation_key: related_result or None})
        return self

    def _map_related(self, related_result, related):
        return related.map_related(related_result)

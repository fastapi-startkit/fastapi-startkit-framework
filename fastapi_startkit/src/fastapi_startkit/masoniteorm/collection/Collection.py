from typing import TYPE_CHECKING, Any, Generator, Generic, TypeVar

from fastapi_startkit.support.collection import Collection as BaseCollection

T = TypeVar("T")


class Collection(BaseCollection, Generic[T]):
    if TYPE_CHECKING:
        # Typing-only element-access overrides so a Collection[User] yields
        # User (not Any) on iteration, indexing, and first(). Runtime behaviour
        # is supplied unchanged by the base class.
        def first(self, callback=None) -> "T | None": ...
        def __iter__(self) -> "Generator[T, Any, None]": ...
        def __getitem__(self, item) -> "T": ...

    def with_relationship_autoloading(self):
        pass

    async def load(self, *relations):
        """Post-query eager loading — equivalent to Collection::load().

        After fetching a collection, call this to load relationships in batch
        without N+1 queries:

            users = await User.get()
            await users.load('posts', 'profile')
        """
        if not self._items:
            return self

        first = self._items[0]
        for relation in relations:
            relationship = getattr(first.__class__, relation)
            result_set = await relationship.get_related(None, self)
            if result_set:
                map_related = relationship.map_related(result_set)
                for model in self._items:
                    if isinstance(result_set, Collection):
                        relationship.register_related(relation, model, map_related)
                    else:
                        # load() only runs on model collections; T is generic.
                        model.add_relation({relation: map_related or None})  # type: ignore

        return self

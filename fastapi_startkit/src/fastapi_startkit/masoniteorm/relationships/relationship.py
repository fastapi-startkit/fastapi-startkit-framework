from collections.abc import Callable
from typing import Any, cast, overload

from .BaseRelationship import BaseRelationship

type RelationFactory = Callable[[Any], BaseRelationship]


class RelationshipMethod:
    def __init__(self, method: "RelationFactory | classmethod[Any, ..., Any]"):
        self.method = cast(RelationFactory, method.__func__ if isinstance(method, classmethod) else method)
        self.attribute = self.method.__name__
        self.relations: dict[type, BaseRelationship] = {}

    def __set_name__(self, owner, name):
        self.attribute = name

    def relation(self, owner: type) -> BaseRelationship:
        if owner not in self.relations:
            relation = self.method(owner)
            relation.__set_name__(owner, self.attribute)
            self.relations[owner] = relation
        return self.relations[owner]

    def __get__(self, instance, owner):
        return self.relation(owner).access(instance, owner)


@overload
def relationship[R](method: "classmethod[Any, [], R]") -> R: ...
@overload
def relationship[R](method: Callable[[Any], R]) -> R: ...
def relationship(method: Any) -> Any:
    return RelationshipMethod(method)

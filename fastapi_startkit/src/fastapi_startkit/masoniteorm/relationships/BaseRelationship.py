import os
import typing
import warnings
from typing import TYPE_CHECKING, Any, ForwardRef, Generic, Self, get_args, overload

from typing_extensions import TypeVar

from fastapi_startkit.masoniteorm.models import registry
from ..collection import Collection
from ..exceptions import LazyLoadingViolation

if TYPE_CHECKING:
    from ..models.model import Model

TModel = TypeVar("TModel", bound="Model", default="Model")
TResult = TypeVar("TResult", default=Any)

type SingleResult[T] = T | None
type ManyResult[T] = Collection[T]


class BaseRelationship(Generic[TModel, TResult]):
    def __init__(self, fn: str | None = None, local_key=None, foreign_key=None):
        self.bind_model(fn)

        self.local_key = local_key
        self.foreign_key = foreign_key
        self.attribute = None

    def __set_name__(self, cls, name):
        self.attribute = name
        self.owner_class = cls
        if "_model_name" in self.__dict__:
            self.model_reference()

    def bind_model(self, fn: str | None) -> None:
        if fn is not None and not isinstance(fn, str):
            raise TypeError(f"Relationship {self.__class__.__name__} expects a string as the first argument")
        if fn is not None:
            klass = self.__class__.__name__
            warnings.warn(
                f'Passing the related model as {klass}("{fn}", ...) is deprecated and will be removed in 1.x; '
                f'declare it as {klass}["{fn}"](...) instead.',
                DeprecationWarning,
                skip_file_prefixes=(os.path.dirname(__file__), typing.__file__),
            )
        self._model_name = fn
        self.fn = self.related_model

    def related_model(self) -> type:
        model = self.model_reference()
        return registry.Registry.resolve(model) if isinstance(model, str) else model

    def model_reference(self) -> str | type:
        if self._model_name is not None:
            return self._model_name

        alias = self.__dict__.get("__orig_class__")
        if alias is None:
            klass = self.__class__.__name__
            owner = self.__dict__.get("owner_class")
            subject = f"{owner.__name__}.{self.__dict__.get('attribute')}" if owner else klass
            raise TypeError(f'{subject} needs its related model: declare it as {klass}["Model"](...)')

        model = get_args(alias)[0]
        return model.__forward_arg__ if isinstance(model, ForwardRef) else model

    def get_builder(self):
        return self.fn()().get_builder()

    @overload
    def __get__(self, instance: None, owner: Any) -> Self: ...
    @overload
    def __get__(self: "BaseRelationship[Model, Any]", instance: object, owner: Any) -> Any: ...
    @overload
    def __get__(self, instance: object, owner: Any) -> TResult: ...
    def __get__(self, instance, owner) -> Any:
        return self.access(instance, owner)

    def access(self, instance, owner):
        """
        This method is called when the decorated method is accessed.

        Arguments:
            instance {object|None} -- The instance we called.
                If we didn't call the attribute and only accessed it then this will be None.

            owner {object} -- The current model that the property was accessed on.

        Returns:
            object -- Either returns a builder or a hydrated model.
        """
        if instance is None:
            return self

        self.set_keys(instance, self.attribute)

        if not instance.is_loaded():
            return self

        if self.attribute in instance._relationships:
            return instance._relationships[self.attribute]

        raise LazyLoadingViolation(instance, self.attribute)

    def __getattr__(self, attribute):
        return getattr(self.get_builder(), attribute)

    def apply_query(self, foreign, owner):
        """Return a dictionary to hydrate the model with

        Arguments:
            foreign {oject} -- The relationship object
            owner {object} -- The current model oject.

        Returns:
            dict -- A dictionary of data which will be hydrated.
        """
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'apply_query' method")

    def query_where_exists(self, builder, callback, method="where_exists"):
        """Adds a criteria clause to the query filter for existing related records"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'query_where_exists' method")

    def joins(self, builder, clause=None):
        """Helper method for adding join clauses to a relationship"""
        other_table = self.get_builder().get_table_name()
        local_table = builder.get_table_name()
        return builder.join(
            other_table,
            f"{local_table}.{self.local_key}",
            "=",
            f"{other_table}.{self.foreign_key}",
            clause=clause,
        )

    def get_with_count_query(self, builder, callback):
        """Adds a clause to the query to get the record count of the relationship"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'get_with_count_query' method")

    def attach(self, current_model, related_record):
        """Link a related model to the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'attach' method")

    def get_related(self, query, relation, eagers=None, callback=None):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'get_related' method")

    def relate(self, related_record):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'relate' method")

    def detach(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'detach' method")

    def attach_related(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'attach_related' method")

    def detach_related(self, current_model, related_record):
        """Unlink a related model from the current model"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'detach_related' method")

    def query_has(self, current_query_builder, method="where_exists"):
        """Adds a clause to the query to check if a relation exists"""
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'query_has' method")

    def map_related(self, related_result):
        klass = self.__class__.__name__
        raise NotImplementedError(f"{klass} relationship does not implement the 'map_related' method")

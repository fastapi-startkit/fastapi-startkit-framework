from typing import Any, Callable, Generic, Protocol, Self, TypeVar, overload
import warnings

from pydantic import Field as BaseField
from pydantic.fields import FieldInfo

from fastapi_startkit.masoniteorm.models.observer import (
    CreatedAtObserver,
    UpdatedAtObserver,
)


T = TypeVar("T")


class _AttributeModel(Protocol):
    def get_attribute(self, key: str) -> Any: ...

    def set_attribute(self, key: str, value: Any) -> None: ...


class FieldDescriptor(Generic[T]):
    """
    A descriptor that wraps Pydantic's FieldInfo.
    It allows us to store metadata that the Caster can later discover.
    """

    def __init__(self, field_info: FieldInfo) -> None:
        self.field_info = field_info
        self.name: str | None = None

    def __set_name__(self, owner: type[_AttributeModel], name: str) -> None:
        self.name = name

    @overload
    def __get__(self, instance: None, owner: type[_AttributeModel]) -> FieldInfo: ...

    @overload
    def __get__(self, instance: _AttributeModel, owner: type[_AttributeModel]) -> T: ...

    def __get__(self, instance: _AttributeModel | None, owner: type[_AttributeModel]) -> T | FieldInfo:
        if instance is None:
            # When accessed on the class (e.g., User.name), return the FieldInfo
            return self.field_info

        # When accessed on the instance (e.g., user.name), retrieve from ORM storage
        assert self.name is not None
        return instance.get_attribute(self.name)

    def __set__(self, instance: _AttributeModel, value: T) -> None:
        # When setting (e.g., user.name = 'Joe'), update ORM storage
        assert self.name is not None
        instance.set_attribute(self.name, value)


class Field(FieldDescriptor[T]):
    """
    Typed ORM field descriptor backed by Pydantic field metadata.

    Required fields can state their type explicitly with ``Field[int]()``.
    Fields with a default infer their type with ``Field(default=False)``.
    """

    @overload
    def __init__(self, *, default: T, default_factory: None = None, **kwargs: Any) -> None: ...

    @overload
    def __init__(self, *, default_factory: Callable[[], T], **kwargs: Any) -> None: ...

    @overload
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(BaseField(*args, **kwargs))


class ModelField(Generic[T]):
    """Deprecated; scheduled for removal in 2.x. Use ``Field[Address]()`` instead."""

    def __init__(self, default: T | None = None) -> None:
        warnings.warn(
            "ModelField is deprecated and will be removed in 2.x; use Field[YourModel]() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.default = default
        self.name: str | None = None

    def __set_name__(self, owner: type[_AttributeModel], name: str) -> None:
        self.name = name

    @overload
    def __get__(self, instance: None, owner: type[_AttributeModel]) -> Self: ...

    @overload
    def __get__(self, instance: _AttributeModel, owner: type[_AttributeModel]) -> T: ...

    def __get__(self, instance: _AttributeModel | None, owner: type[_AttributeModel]) -> T | Self:
        if instance is None:
            return self
        assert self.name is not None
        return instance.get_attribute(self.name)

    def __set__(self, instance: _AttributeModel, value: T) -> None:
        assert self.name is not None
        instance.set_attribute(self.name, value)


class DateTimeField:
    def __init__(self, fmt: str = "YYYY-MM-DD HH:mm:ss", tz: str = "UTC"):
        self.format = fmt
        self.tz = tz

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return instance.get_attribute(self.name)

    # def __set__(self, instance, value):
    #     instance.set_attribute(self.name, value)


class CreatedAtField:
    def __init__(self, fmt: str = "YYYY-MM-DD HH:mm:ss", tz: str = "UTC"):
        self.format = fmt
        self.tz = tz

    def __set_name__(self, owner, name):
        self.name = name
        owner.observe(CreatedAtObserver(name, self.format, self.tz))

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.get_attribute(self.name)

    # def __set__(self, instance, value):
    #     instance.set_value(self.name, value)


class UpdatedAtField:
    def __init__(self, fmt: str = "YYYY-MM-DD HH:mm:ss", tz: str = "UTC"):
        self.format = fmt
        self.tz = tz

    def __set_name__(self, owner, name):
        self.name = name
        owner.observe(UpdatedAtObserver(name, self.format, self.tz))

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.get_attribute(self.name)

    def __set__(self, instance, value):
        instance.set_value(self.name, value)

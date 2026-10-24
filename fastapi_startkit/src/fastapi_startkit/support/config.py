from dataclasses import Field, MISSING, dataclass
from typing import TypeVar, cast

from fastapi_startkit.environment import value

T = TypeVar("T")


class _ConfigMeta(type):
    def __call__(cls: type[T], *args: object, **kwargs: object) -> T:
        _ConfigMeta.ensure_dataclass(cls)
        resolved_args = [value(argument) for argument in args]
        resolved_kwargs = {name: value(argument) for name, argument in kwargs.items()}
        return cast(T, type.__call__(cls, *resolved_args, **resolved_kwargs))

    @staticmethod
    def ensure_dataclass(cls: type) -> None:
        for klass in reversed(cls.__mro__):
            if isinstance(klass, _ConfigMeta) and "__dataclass_fields__" not in klass.__dict__:
                dataclass(klass)

    def __getattr__(cls, name: str) -> object:
        try:
            fields = cast(dict[str, Field[object]], type.__getattribute__(cls, "__dataclass_fields__"))
        except AttributeError:
            raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}") from None
        field = fields.get(name)
        if field is not None and field.default_factory is not MISSING:
            return field.default_factory()
        raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}")


class Config(metaclass=_ConfigMeta):
    pass

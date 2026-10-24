from dataclasses import Field, MISSING, dataclass
from threading import Lock
from typing import TypeVar, cast

from fastapi_startkit.environment import value

T = TypeVar("T")

_dataclass_lock = Lock()


class _ConfigMeta(type):
    def __call__(cls: type[T], *args: object, **kwargs: object) -> T:
        _ConfigMeta.ensure_dataclass(cls.__mro__)
        resolved_args = [value(argument) for argument in args]
        resolved_kwargs = {name: value(argument) for name, argument in kwargs.items()}
        return cast(T, type.__call__(cls, *resolved_args, **resolved_kwargs))

    @staticmethod
    def ensure_dataclass(classes: tuple[type, ...]) -> None:
        pending = [klass for klass in reversed(classes) if _ConfigMeta.needs_dataclass(klass)]
        if not pending:
            return
        with _dataclass_lock:
            for klass in pending:
                if _ConfigMeta.needs_dataclass(klass):
                    dataclass(eq=False, frozen=_ConfigMeta.has_frozen_base(klass))(klass)

    @staticmethod
    def needs_dataclass(klass: type) -> bool:
        return (
            isinstance(klass, _ConfigMeta)
            and "__dataclass_fields__" not in klass.__dict__
            and any(isinstance(attribute, Field) for attribute in klass.__dict__.values())
        )

    @staticmethod
    def has_frozen_base(klass: type) -> bool:
        params = getattr(klass, "__dataclass_params__", None)
        return params is not None and params.frozen

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
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _ConfigMeta.ensure_dataclass(cls.__mro__[1:])

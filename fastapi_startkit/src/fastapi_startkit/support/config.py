from copy import deepcopy
from dataclasses import Field, MISSING, dataclass, field
from functools import partial
from threading import Lock
from typing import TypeVar, cast

from fastapi_startkit.environment import value

try:
    from annotationlib import Format, get_annotations

    def _own_annotations(klass: type) -> dict[str, object]:
        return get_annotations(klass, format=Format.FORWARDREF)

except ImportError:

    def _own_annotations(klass: type) -> dict[str, object]:
        return klass.__dict__.get("__annotations__", {})


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
                    _ConfigMeta.copy_unhashable_defaults(klass)
                    dataclass(eq=False, frozen=_ConfigMeta.has_frozen_base(klass))(klass)

    @staticmethod
    def needs_dataclass(klass: type) -> bool:
        if not isinstance(klass, _ConfigMeta) or "__dataclass_fields__" in klass.__dict__:
            return False
        if any(isinstance(attribute, Field) for attribute in klass.__dict__.values()):
            return True
        names = _own_annotations(klass)
        return bool(names) and all(name in klass.__dict__ for name in names)

    @staticmethod
    def copy_unhashable_defaults(klass: type) -> None:
        for name in _own_annotations(klass):
            default = klass.__dict__.get(name, MISSING)
            if default is not MISSING and not isinstance(default, Field) and type(default).__hash__ is None:
                setattr(klass, name, field(default_factory=partial(deepcopy, default)))

    @staticmethod
    def has_frozen_base(klass: type) -> bool:
        params = getattr(klass, "__dataclass_params__", None)
        return params is not None and params.frozen

    def __getattr__(cls, name: str) -> object:
        try:
            fields = cast(dict[str, Field[object]], type.__getattribute__(cls, "__dataclass_fields__"))
        except AttributeError:
            raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}") from None
        declared = fields.get(name)
        if declared is not None and declared.default_factory is not MISSING:
            return declared.default_factory()
        raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}")


class Config(metaclass=_ConfigMeta):
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _ConfigMeta.ensure_dataclass(cls.__mro__[1:])

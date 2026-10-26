from copy import copy
from dataclasses import Field, MISSING, dataclass, field
from typing import TypeVar, cast, dataclass_transform
from weakref import WeakKeyDictionary

from fastapi_startkit.environment import value

T = TypeVar("T")

_DATACLASS_PARAMS = "__dataclass_params__"
_pre_dataclass_namespaces: WeakKeyDictionary[type, dict[str, object]] = WeakKeyDictionary()


def _copy_fields(namespace: dict[str, object]) -> dict[str, object]:
    return {
        name: copy(attribute) if isinstance(attribute, Field) else attribute for name, attribute in namespace.items()
    }


def _has_frozen_base(klass: type) -> bool:
    params = getattr(klass, _DATACLASS_PARAMS, None)
    return params is not None and params.frozen


class _ConfigMeta(type):
    def __call__(cls: type[T], *args: object, **kwargs: object) -> T:
        resolved_args = [value(argument) for argument in args]
        resolved_kwargs = {name: value(argument) for name, argument in kwargs.items()}
        return cast(T, type.__call__(cls, *resolved_args, **resolved_kwargs))

    def __setattr__(cls, name: str, attribute: object) -> None:
        if name == _DATACLASS_PARAMS:
            namespace = _pre_dataclass_namespaces.pop(cls, None)
            if namespace is not None:
                _ConfigMeta.restore_namespace(cls, namespace)
        super().__setattr__(name, attribute)

    @staticmethod
    def restore_namespace(klass: type, namespace: dict[str, object]) -> None:
        for name in [name for name in klass.__dict__ if name not in namespace]:
            type.__delattr__(klass, name)
        for name, attribute in _copy_fields(namespace).items():
            if klass.__dict__.get(name, MISSING) is not namespace[name]:
                type.__setattr__(klass, name, attribute)

    def __getattr__(cls, name: str) -> object:
        try:
            fields = cast(dict[str, Field[object]], type.__getattribute__(cls, "__dataclass_fields__"))
        except AttributeError:
            raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}") from None
        declared = fields.get(name)
        if declared is not None and declared.default_factory is not MISSING:
            return declared.default_factory()
        raise AttributeError(f"{cls.__name__!r} has no attribute {name!r}")


@dataclass_transform(eq_default=False, field_specifiers=(field, Field))
class Config(metaclass=_ConfigMeta):
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "__dataclass_fields__" in cls.__dict__:
            return
        namespace = _copy_fields(dict(cls.__dict__))
        dataclass(eq=False, frozen=_has_frozen_base(cls))(cls)
        _pre_dataclass_namespaces[cls] = namespace

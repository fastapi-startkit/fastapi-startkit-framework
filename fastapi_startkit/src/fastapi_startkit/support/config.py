from copy import copy
from dataclasses import Field, MISSING, dataclass, field
from typing import TypeVar, cast, dataclass_transform
from weakref import WeakKeyDictionary

from fastapi_startkit.environment import value

T = TypeVar("T")

_DATACLASS_PARAMS = "__dataclass_params__"
_OWN_ANNOTATION_KEYS = ("__annotations__", "__annotate_func__")

_Changes = dict[str, tuple[object, object]]
_automatic_changes: WeakKeyDictionary[type, _Changes] = WeakKeyDictionary()


def _snapshot(klass: type) -> dict[str, object]:
    return {
        name: copy(attribute) if isinstance(attribute, Field) else attribute
        for name, attribute in klass.__dict__.items()
    }


def _changes(before: dict[str, object], klass: type) -> _Changes:
    after = dict(klass.__dict__)
    return {
        name: (after.get(name, MISSING), before.get(name, MISSING))
        for name in before.keys() | after.keys()
        if after.get(name, MISSING) is not before.get(name, MISSING)
    }


def _declares_annotations(klass: type) -> bool:
    return any(key in klass.__dict__ for key in _OWN_ANNOTATION_KEYS)


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
            changes = _automatic_changes.pop(cls, None)
            if changes is not None:
                _ConfigMeta.undo_automatic_pass(cls, changes)
        super().__setattr__(name, attribute)

    @staticmethod
    def undo_automatic_pass(klass: type, changes: _Changes) -> None:
        for name, (after, before) in changes.items():
            if klass.__dict__.get(name, MISSING) is not after:
                continue
            if before is MISSING:
                type.__delattr__(klass, name)
            else:
                type.__setattr__(klass, name, copy(before) if isinstance(before, Field) else before)

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
        if "__dataclass_fields__" in cls.__dict__ or not _declares_annotations(cls):
            return
        before = _snapshot(cls)
        dataclass(eq=False, frozen=_has_frozen_base(cls))(cls)
        _automatic_changes[cls] = _changes(before, cls)

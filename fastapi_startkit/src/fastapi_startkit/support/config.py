import sys
from collections.abc import Mapping
from dataclasses import Field, InitVar, MISSING, dataclass, field
from threading import Lock
from typing import ClassVar, TypeVar, cast, get_origin

from fastapi_startkit.environment import value

if sys.version_info >= (3, 14):
    from annotationlib import Format, get_annotations

    def _own_annotations(klass: type) -> Mapping[str, object]:
        return get_annotations(klass, format=Format.FORWARDREF)

else:

    def _own_annotations(klass: type) -> Mapping[str, object]:
        return klass.__dict__.get("__annotations__", {})


T = TypeVar("T")

_dataclass_lock = Lock()
_COPIED_DEFAULT_TYPES = (dict, list, set)


def _resolve_string_annotation(klass: type, annotation: str) -> object:
    module = sys.modules.get(klass.__module__)
    namespace = vars(module) if module is not None else {}
    owner, _, name = annotation.split("[", 1)[0].strip().rpartition(".")
    if owner:
        return getattr(namespace.get(owner), name, None)
    return namespace.get(name)


def _is_pseudo_field(klass: type, annotation: object) -> bool:
    if isinstance(annotation, str):
        annotation = _resolve_string_annotation(klass, annotation)
    return (
        isinstance(annotation, InitVar) or annotation is InitVar or (get_origin(annotation) or annotation) is ClassVar
    )


def _field_names(klass: type) -> list[str]:
    return [name for name, annotation in _own_annotations(klass).items() if not _is_pseudo_field(klass, annotation)]


def _is_hashable(default: object) -> bool:
    return type(default).__hash__ is not None


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
                    _ConfigMeta.copy_container_defaults(klass)
                    dataclass(eq=False, frozen=_ConfigMeta.has_frozen_base(klass))(klass)

    @staticmethod
    def needs_dataclass(klass: type) -> bool:
        if not isinstance(klass, _ConfigMeta) or "__dataclass_fields__" in klass.__dict__:
            return False
        if _ConfigMeta.has_custom_init(klass):
            return False
        if _ConfigMeta.declares_field(klass):
            return True
        defaults = [klass.__dict__.get(name, MISSING) for name in _field_names(klass)]
        return bool(defaults) and all(default is not MISSING and _is_hashable(default) for default in defaults)

    @staticmethod
    def declares_field(klass: type) -> bool:
        return any(isinstance(attribute, Field) for attribute in klass.__dict__.values())

    @staticmethod
    def has_custom_init(klass: type) -> bool:
        for base in klass.__mro__:
            if "__init__" in base.__dict__:
                return base is not object and "__dataclass_fields__" not in base.__dict__
        return False

    @staticmethod
    def copy_container_defaults(klass: type) -> None:
        if not _ConfigMeta.declares_field(klass):
            return
        for name in _field_names(klass):
            default = klass.__dict__.get(name, MISSING)
            if type(default) in _COPIED_DEFAULT_TYPES:
                setattr(klass, name, field(default_factory=cast(dict[object, object], default).copy))

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

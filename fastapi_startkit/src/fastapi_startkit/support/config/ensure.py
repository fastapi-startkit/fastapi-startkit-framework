from typing import cast


def ensure_config[T](owner: str, source: object, protocol: type[T]) -> T:
    if isinstance(source, protocol):
        return source
    missing = ", ".join(name for name in protocol_members(protocol) if not hasattr(source, name))
    raise TypeError(f"{owner} requires {protocol.__name__}; missing attributes: {missing}")


def protocol_members(protocol: type) -> list[str]:
    members = cast(set[str], getattr(protocol, "__protocol_attrs__", set()))
    declared = [
        name for base in reversed(protocol.__mro__) for name in (*getattr(base, "__annotations__", {}), *vars(base))
    ]
    return [name for name in dict.fromkeys(declared) if name in members]

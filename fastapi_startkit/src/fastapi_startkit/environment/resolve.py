from dataclasses import Field, MISSING
from typing import Any


def resolve(item: Any) -> Any:
    if isinstance(item, Field):
        if item.default_factory is MISSING:
            return item
        return resolve(item.default_factory())
    if isinstance(item, dict):
        return {key: resolve(entry) for key, entry in item.items()}
    if isinstance(item, list):
        return [resolve(entry) for entry in item]
    if isinstance(item, tuple):
        return tuple(resolve(entry) for entry in item)
    return item

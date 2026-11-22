from copy import copy
from dataclasses import Field, MISSING
from typing import Any


def resolve(item: Any) -> Any:
    if isinstance(item, Field):
        if item.default_factory is MISSING:
            return item
        return resolve(item.default_factory())
    if isinstance(item, dict):
        entries = {key: resolve(entry) for key, entry in item.items()}
        if all(entries[key] is entry for key, entry in item.items()):
            return item
        clone = copy(item)
        clone.update(entries)
        return clone
    if isinstance(item, list):
        entries = [resolve(entry) for entry in item]
        if all(new is old for new, old in zip(entries, item)):
            return item
        clone = copy(item)
        clone[:] = entries
        return clone
    if isinstance(item, tuple):
        entries = tuple(resolve(entry) for entry in item)
        if all(new is old for new, old in zip(entries, item)):
            return item
        return item._make(entries) if hasattr(item, "_make") else type(item)(entries)
    return item

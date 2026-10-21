from inspect import isawaitable
from typing import Any


class ObservesEvents:
    __has_events__: bool
    __observers__: dict[type, list[Any]]

    async def observe_events(self, model, event):
        if not model.__has_events__:
            return

        for klass in type(model).__mro__:
            for observer in model.__observers__.get(klass, []):
                handler = getattr(observer, event, None)
                if handler is None:
                    continue

                result = handler(model)
                if isawaitable(result):
                    await result

    @classmethod
    def observe(cls, observer):
        if cls in cls.__observers__:
            cls.__observers__[cls].append(observer)
        else:
            cls.__observers__.update({cls: [observer]})

    @classmethod
    def without_events(cls):
        """Sets __has_events__ attribute on model to false."""
        cls.__has_events__ = False
        return cls

    @classmethod
    def with_events(cls):
        """Sets __has_events__ attribute on model to True."""
        cls.__has_events__ = True
        return cls

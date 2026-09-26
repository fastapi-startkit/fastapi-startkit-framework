import json
from collections.abc import Callable
from typing import Any


class BasePaginator:
    result: Any
    serialize: Callable[..., Any]

    def __iter__(self):
        for result in self.result:
            yield result

    def to_json(self):
        return json.dumps(self.serialize())

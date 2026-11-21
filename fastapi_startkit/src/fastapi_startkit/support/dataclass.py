from typing import Any

import dataclasses

from fastapi_startkit.environment import resolve


class Dataclass:
    @staticmethod
    def to_dict(obj: Any):
        obj = resolve(obj) if isinstance(obj, dataclasses.Field) else obj
        if hasattr(obj, "model_dump") and callable(obj.model_dump):
            return obj.model_dump()
        if dataclasses.is_dataclass(obj):
            return {f.name: Dataclass.to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, dict):
            return {k: Dataclass.to_dict(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [Dataclass.to_dict(v) for v in obj]
        return obj

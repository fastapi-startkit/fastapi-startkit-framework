from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.schema import Schema


class Migration:
    def __init__(self, connection: str, schema: Schema):
        self.connection = connection

        self.schema = schema

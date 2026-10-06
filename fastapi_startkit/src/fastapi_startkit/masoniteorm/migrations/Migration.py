from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.schema import Schema


class Migration:
    connection: str
    schema: Schema

    def __init__(self, connection=None, schema=None):
        self.connection = connection

        self.schema = schema

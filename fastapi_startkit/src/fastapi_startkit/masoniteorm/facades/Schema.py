from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.schema.schema import Schema as SchemaBuilder
    from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint


class Schema:
    _instance: "SchemaBuilder | None" = None

    @classmethod
    def instance(cls) -> "SchemaBuilder":
        if cls._instance is None:
            from fastapi_startkit.application import app

            cls._instance = app().make("schema")
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def on(cls, connection_name: str) -> "SchemaBuilder":
        return cls.instance().on(connection_name)

    @classmethod
    async def has_table(cls, table: str) -> bool:
        return await cls.instance().has_table(table)

    @classmethod
    async def get_all_tables(cls) -> list[str]:
        return await cls.instance().get_all_tables()

    @classmethod
    async def create(cls, table: str) -> "Blueprint":
        return await cls.instance().create(table)

    @classmethod
    async def create_table_if_not_exists(cls, table: str) -> "Blueprint":
        return await cls.instance().create_table_if_not_exists(table)

    @classmethod
    async def table(cls, table: str) -> "Blueprint":
        return await cls.instance().table(table)

    @classmethod
    async def drop_table(cls, table: str) -> None:
        return await cls.instance().drop_table(table)

    @classmethod
    async def drop_table_if_exists(cls, table: str) -> None:
        return await cls.instance().drop_table_if_exists(table)

    @classmethod
    async def rename(cls, table: str, new_name: str) -> None:
        return await cls.instance().rename(table, new_name)

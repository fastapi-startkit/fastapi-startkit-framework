from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.connections.connection import AfterCommitCallback, Connection
    from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
    from fastapi_startkit.masoniteorm.models.builder import QueryBuilder


class DB:
    _instance: "DatabaseManager | None" = None

    @classmethod
    def instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            from fastapi_startkit.application import app

            cls._instance = app().make("db")
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def connection(cls, name: str | None = None) -> "Connection":
        return cls.instance().connection(name)

    @classmethod
    def table(cls, name: str) -> "QueryBuilder":
        builder = cls.instance().connection(None).query()
        builder._table = name
        return builder

    @classmethod
    async def select(cls, query: str, bindings: list | None = None) -> list[dict]:
        return await cls.instance().connection(None).select(query, bindings)

    @classmethod
    async def select_one(cls, query: str, bindings: list | None = None) -> dict | None:
        return await cls.instance().connection(None).select_one(query, bindings)

    @classmethod
    async def insert(cls, query: str, bindings: list | None = None) -> int | None:
        return await cls.instance().connection(None).insert(query, bindings)

    @classmethod
    async def update(cls, query: str, bindings: list | None = None) -> int:
        return await cls.instance().connection(None).update(query, bindings)

    @classmethod
    async def delete(cls, query: str, bindings: list | None = None) -> int:
        return await cls.instance().connection(None).delete(query, bindings)

    @classmethod
    async def statement(cls, query: str, bindings: list | None = None) -> bool:
        return await cls.instance().connection(None).statement(query, bindings)

    @classmethod
    async def begin_transaction(cls, name: str | None = None) -> None:
        await cls.instance().connection(name).begin_transaction()

    @classmethod
    async def commit(cls, name: str | None = None) -> None:
        await cls.instance().connection(name).commit_transaction()

    @classmethod
    async def rollback(cls, name: str | None = None) -> None:
        await cls.instance().connection(name).rollback()

    @classmethod
    async def after_commit(cls, callback: AfterCommitCallback, name: str | None = None) -> None:
        await cls.instance().connection(name).after_commit(callback)

from fastapi_startkit.configuration import config
from fastapi_startkit.masoniteorm.migrations import Migration


def table_name() -> str:
    return config("cache.stores.database.table") or "caches"


class CreateCachesTable(Migration):
    async def up(self):
        async with await self.schema.create(table_name()) as table:
            table.string("key").primary()
            table.text("value")
            table.big_integer("expiration").nullable()

    async def down(self):
        await self.schema.drop(table_name())

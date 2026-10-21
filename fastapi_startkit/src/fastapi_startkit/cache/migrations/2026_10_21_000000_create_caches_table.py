from fastapi_startkit.masoniteorm.migrations import Migration


class CreateCachesTable(Migration):
    async def up(self):
        async with await self.schema.create("caches") as table:
            table.string("key").primary()
            table.text("value")
            table.integer("expiration").nullable()

    async def down(self):
        await self.schema.drop("caches")

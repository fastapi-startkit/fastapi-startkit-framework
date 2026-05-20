from fastapi_startkit.masoniteorm.migrations import Migration


class CreatePostsTable(Migration):
    async def up(self):
        async with await self.schema.create("posts") as table:
            table.id()
            table.string("title")
            table.timestamps()

    async def down(self):
        await self.schema.drop("posts")

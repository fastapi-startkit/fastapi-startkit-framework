from fastapi_startkit.masoniteorm import Migration


class AddBodyToPostsTable(Migration):
    async def up(self):
        async with await self.schema.table("posts") as table:
            table.text("body").nullable()

    async def down(self):
        async with await self.schema.table("posts") as table:
            table.drop_column("body")

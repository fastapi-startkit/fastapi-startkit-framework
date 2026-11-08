from fastapi_startkit.masoniteorm import Migration


class CreateUsersTable(Migration):
    async def up(self):
        async with await self.schema.create("users") as table:
            table.increments("id")
            table.string("name")
            table.string("email").unique()
            table.string("password")
            table.timestamps()

    async def down(self):
        await self.schema.drop("users")

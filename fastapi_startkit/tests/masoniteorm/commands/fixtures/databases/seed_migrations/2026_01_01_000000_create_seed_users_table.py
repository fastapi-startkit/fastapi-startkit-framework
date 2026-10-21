from fastapi_startkit.masoniteorm import Migration


class CreateSeedUsersTable(Migration):
    async def up(self):
        async with await self.schema.create("seed_users") as table:
            table.id()
            table.string("name")

    async def down(self):
        await self.schema.drop("seed_users")

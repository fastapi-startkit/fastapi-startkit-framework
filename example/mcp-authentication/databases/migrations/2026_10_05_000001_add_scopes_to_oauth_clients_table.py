from fastapi_startkit.masoniteorm.migrations import Migration


class AddScopesToOauthClientsTable(Migration):
    async def up(self):
        async with await self.schema.table("oauth_clients") as table:
            table.text("scopes").nullable()

    async def down(self):
        async with await self.schema.table("oauth_clients") as table:
            table.drop_column("scopes")

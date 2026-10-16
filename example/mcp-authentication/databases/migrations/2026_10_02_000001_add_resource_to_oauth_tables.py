from fastapi_startkit.masoniteorm.migrations import Migration


class AddResourceToOauthTables(Migration):
    async def up(self):
        async with await self.schema.table("oauth_auth_codes") as table:
            table.text("resource").nullable()
        async with await self.schema.table("oauth_refresh_tokens") as table:
            table.text("resource").nullable()

    async def down(self):
        async with await self.schema.table("oauth_refresh_tokens") as table:
            table.drop_column("resource")
        async with await self.schema.table("oauth_auth_codes") as table:
            table.drop_column("resource")

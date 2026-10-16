from fastapi_startkit.masoniteorm.migrations import Migration


class CreateOauthAccessTokensTable(Migration):
    async def up(self):
        async with await self.schema.create("oauth_access_tokens") as table:
            table.string("jti").primary()
            table.text("user_id").nullable()
            table.string("client_id").nullable()
            table.text("scopes")
            table.double("expires_at").nullable()
            table.boolean("revoked").default(False)
            table.string("name").nullable()
            table.boolean("personal_access").default(False)
            table.double("created_at")
            table.index("user_id")
            table.index("expires_at")

    async def down(self):
        await self.schema.drop("oauth_access_tokens")

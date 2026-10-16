from fastapi_startkit.masoniteorm.migrations import Migration


class CreateOauthRefreshTokensTable(Migration):
    async def up(self):
        async with await self.schema.create("oauth_refresh_tokens") as table:
            table.string("token_hash", 64).primary()
            table.string("access_jti")
            table.text("user_id").nullable()
            table.string("client_id").nullable()
            table.text("scopes")
            table.double("expires_at").nullable()
            table.boolean("revoked").default(False)
            table.double("created_at")
            table.index("expires_at")

    async def down(self):
        await self.schema.drop("oauth_refresh_tokens")

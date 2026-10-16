from fastapi_startkit.masoniteorm.migrations import Migration


class CreateOauthAuthCodesTable(Migration):
    async def up(self):
        async with await self.schema.create("oauth_auth_codes") as table:
            table.string("code_hash", 64).primary()
            table.string("client_id")
            table.text("user_id").nullable()
            table.text("scopes")
            table.text("redirect_uri").nullable()
            table.string("code_challenge").nullable()
            table.string("code_challenge_method", 32).nullable()
            table.double("expires_at")

    async def down(self):
        await self.schema.drop("oauth_auth_codes")

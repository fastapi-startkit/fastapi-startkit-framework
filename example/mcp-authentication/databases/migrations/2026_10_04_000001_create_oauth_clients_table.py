from fastapi_startkit.masoniteorm.migrations import Migration


class CreateOauthClientsTable(Migration):
    async def up(self):
        async with await self.schema.create("oauth_clients") as table:
            table.string("id").primary()
            table.string("name")
            table.string("secret").nullable()
            table.text("redirect_uris")
            table.boolean("confidential").default(True)
            table.text("grant_types")
            table.boolean("revoked").default(False)
            table.string("provider").nullable()
            table.double("created_at")

    async def down(self):
        await self.schema.drop("oauth_clients")

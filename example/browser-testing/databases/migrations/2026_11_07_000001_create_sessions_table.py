from fastapi_startkit.masoniteorm.migrations import Migration


class CreateSessionsTable(Migration):
    async def up(self):
        async with await self.schema.create("sessions") as table:
            table.string("id").primary()
            table.text("user_id").nullable()
            table.string("guard")
            table.string("csrf_token")
            table.double("created_at")
            table.double("last_activity")
            table.double("expires_at").nullable()
            table.index("expires_at")

    async def down(self):
        await self.schema.drop("sessions")

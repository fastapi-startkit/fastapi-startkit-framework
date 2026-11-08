from fastapi_startkit.configuration import config
from fastapi_startkit.masoniteorm.migrations import Migration


def table_name() -> str:
    return config("notifications.table") or "notifications"


class CreateNotificationsTable(Migration):
    async def up(self):
        async with await self.schema.create(table_name()) as table:
            table.string("id").primary()
            table.string("type")
            table.string("notifiable_type")
            table.string("notifiable_id")
            table.text("data")
            table.timestamp("read_at").nullable()
            table.timestamps()
            table.index(["notifiable_type", "notifiable_id"])

    async def down(self):
        await self.schema.drop(table_name())

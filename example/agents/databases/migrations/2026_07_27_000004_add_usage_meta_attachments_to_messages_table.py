"""AddUsageMetaAttachmentsToMessagesTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class AddUsageMetaAttachmentsToMessagesTable(Migration):
    async def up(self):
        """Run the migrations."""
        async with await self.schema.table("messages") as table:
            table.jsonb("usage").nullable()  # token counts: {"input": n, "output": n}
            table.jsonb("meta").nullable()  # anything per-message: latency, model, node
            table.jsonb("attachments").nullable()  # documents sent with the message

    async def down(self):
        """Revert the migrations."""
        async with await self.schema.table("messages") as table:
            table.drop_column("usage")
            table.drop_column("meta")
            table.drop_column("attachments")

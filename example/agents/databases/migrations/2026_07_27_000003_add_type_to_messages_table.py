"""AddTypeToMessagesTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class AddTypeToMessagesTable(Migration):
    async def up(self):
        """Run the migrations."""
        async with await self.schema.table("messages") as table:
            # What the row is: text | tool_call | tool_response | web_search.
            # Existing rows default to text; tool responses are backfilled below.
            table.string("type", length=20).default("text")

        from app.models.message import Message

        await Message.where("data_type", "json").update({"type": "tool_response"})

    async def down(self):
        """Revert the migrations."""
        async with await self.schema.table("messages") as table:
            table.drop_column("type")

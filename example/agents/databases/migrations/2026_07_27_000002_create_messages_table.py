"""CreateMessagesTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateMessagesTable(Migration):
    async def up(self):
        """Run the migrations."""
        async with await self.schema.create("messages") as table:
            table.increments("id")
            table.string("thread_id")
            table.string("role", length=10)  # user | ai
            table.json("data")  # holds either a JSON payload (job cards) or a JSON string (prose)
            table.string("data_type", length=10)  # string | json
            table.string("run_id").nullable()  # LangGraph run id; null for user messages
            table.timestamps()

            table.index("thread_id")
            table.foreign("thread_id").references("id").on("threads").on_delete("cascade")

    async def down(self):
        """Revert the migrations."""
        await self.schema.drop("messages")

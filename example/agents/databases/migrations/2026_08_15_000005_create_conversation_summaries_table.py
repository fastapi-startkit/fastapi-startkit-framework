"""CreateConversationSummariesTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateConversationSummariesTable(Migration):
    async def up(self):
        """Run the migrations."""
        async with await self.schema.create("conversation_summaries") as table:
            table.increments("id")
            table.string("thread_id")
            table.string("algorithm", length=30)  # user_queries | sliding_window
            table.integer("through_id")  # last messages.id this summary covers
            table.text("summary")
            table.timestamps()

            table.index("thread_id")
            table.foreign("thread_id").references("id").on("threads").on_delete("cascade")

    async def down(self):
        """Revert the migrations."""
        await self.schema.drop("conversation_summaries")

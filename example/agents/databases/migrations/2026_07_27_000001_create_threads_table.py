"""CreateThreadsTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateThreadsTable(Migration):
    async def up(self):
        """Run the migrations."""
        async with await self.schema.create("threads") as table:
            # id is the conversation key (same value as the LangGraph checkpointer thread_id).
            table.string("id").primary()
            table.string("title").nullable()
            table.timestamps()

    async def down(self):
        """Revert the migrations."""
        await self.schema.drop("threads")

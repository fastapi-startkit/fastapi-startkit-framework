"""CreateLessonsTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateLessonsTable(Migration):
    async def up(self):
        """
        Run the migrations.
        """
        async with await self.schema.create("lessons") as table:
            table.increments("id")
            table.integer("course_id").unsigned()
            table.foreign("course_id").references("id").on("courses").on_delete(
                "cascade"
            )
            table.string("title")
            table.timestamps()

    async def down(self):
        """
        Revert the migrations.
        """
        await self.schema.drop("lessons")

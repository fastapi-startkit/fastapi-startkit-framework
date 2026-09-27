"""CreateCourseUserTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateCourseUserTable(Migration):
    async def up(self):
        """
        Run the migrations.
        """
        async with await self.schema.create("course_user") as table:
            table.increments("id")
            table.integer("user_id").unsigned()
            table.foreign("user_id").references("id").on("users").on_delete("cascade")
            table.integer("course_id").unsigned()
            table.foreign("course_id").references("id").on("courses").on_delete(
                "cascade"
            )
            table.integer("progress").default(0)
            table.timestamp("completed_at").nullable()
            table.timestamps()

    async def down(self):
        """
        Revert the migrations.
        """
        await self.schema.drop("course_user")

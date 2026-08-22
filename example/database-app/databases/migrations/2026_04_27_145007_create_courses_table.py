"""CreateCoursesTable Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateCoursesTable(Migration):
    async def up(self):
        """
        Run the migrations.
        """
        async with await self.schema.create("courses") as table:
            table.increments("id")
            table.string("title")
            table.integer("instructor_id").unsigned()
            table.foreign("instructor_id").references("id").on("users").on_delete(
                "cascade"
            )
            table.integer("category_id").unsigned().nullable()
            table.foreign("category_id").references("id").on("categories").on_delete(
                "set null"
            )
            table.timestamps()

    async def down(self):
        """
        Revert the migrations.
        """
        await self.schema.drop("courses")

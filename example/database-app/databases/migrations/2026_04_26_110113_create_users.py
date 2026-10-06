"""Create-users Migration."""

from fastapi_startkit.masoniteorm import Migration


class CreateUsers(Migration):
    async def up(self):
        """
        Run the migrations.
        """
        async with await self.schema.create("users") as table:
            table.increments("id")
            table.string("email").unique()
            table.string("password")
            table.string("name")
            table.string("role", length=50).default("student")

            table.timestamps()

    async def down(self):
        """
        Revert the migrations.
        """
        await self.schema.drop("users")

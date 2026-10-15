import asyncio
from fastapi_startkit.console import Command


class ListUsersCommand(Command):
    name = "users:list"
    description = "List all users from the users table."

    def handle(self):
        asyncio.run(self.handle_async())

    async def handle_async(self):
        from app.models.user import User

        users = await User.get()

        if not users:
            self.line("<comment>No users found.</comment>")
            return

        self.line(f"<info>Found {len(users)} user(s):</info>")
        self.line("")
        self.line(f"{'ID':<6} {'Name':<30} {'Email':<40}")
        self.line("-" * 76)
        for user in users:
            self.line(f"{user.id:<6} {user.name:<30} {user.email:<40}")

from fastapi_startkit.masoniteorm.seeders import Seeder

from ...models import SeededUser


class UserTableSeeder(Seeder):
    async def run(self):
        await SeededUser.create({"name": "user-table-seeder"})

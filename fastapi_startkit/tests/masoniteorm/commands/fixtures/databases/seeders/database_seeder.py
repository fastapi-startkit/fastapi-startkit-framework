from fastapi_startkit.masoniteorm.seeders import Seeder

from ...models import SeededUser


class DatabaseSeeder(Seeder):
    async def run(self):
        await SeededUser.create({"name": "database-seeder"})

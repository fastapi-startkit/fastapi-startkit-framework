from fastapi_startkit.masoniteorm.seeders import Seeder

from ...models import SeededUser


class SpecialSeeder(Seeder):
    async def run(self):
        await SeededUser.create({"name": "special-seeder"})

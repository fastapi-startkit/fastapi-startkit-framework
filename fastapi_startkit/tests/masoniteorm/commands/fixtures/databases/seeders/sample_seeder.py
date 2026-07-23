from fastapi_startkit.masoniteorm.seeders import Seeder

from ...models import SeededUser


class SampleSeeder(Seeder):
    async def run(self):
        await SeededUser.create({"name": "sample-seeder"})

from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class SampleSeeder(Seeder):
    async def run(self):
        CALLS.append(("sample", self.connection))

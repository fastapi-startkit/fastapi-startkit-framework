from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class FirstSeeder(Seeder):
    async def run(self):
        CALLS.append(("first", self.connection))

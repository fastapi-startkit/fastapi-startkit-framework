from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class SecondSeeder(Seeder):
    async def run(self):
        CALLS.append(("second", self.connection))

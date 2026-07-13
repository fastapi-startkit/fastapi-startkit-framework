from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class SpecialSeeder(Seeder):
    async def run(self):
        CALLS.append(("special", self.connection))

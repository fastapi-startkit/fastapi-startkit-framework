from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class DatabaseSeeder(Seeder):
    async def run(self):
        CALLS.append(("database", self.connection))

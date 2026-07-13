from fastapi_startkit.masoniteorm.seeders import Seeder

from .first_seeder import FirstSeeder
from .recorder import CALLS
from .second_seeder import SecondSeeder


class DatabaseSeeder(Seeder):
    async def run(self):
        CALLS.append(("database_seeder_start", self.connection))
        await self.call(FirstSeeder, SecondSeeder)

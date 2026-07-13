from fastapi_startkit.masoniteorm.seeders import Seeder

from .recorder import CALLS


class UserTableSeeder(Seeder):
    async def run(self):
        CALLS.append(("user_table", self.connection))

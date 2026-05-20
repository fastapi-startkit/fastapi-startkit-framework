import pydoc


class Seeder:
    def __init__(self, seed_path="databases/seeds", connection=None):
        self.ran_seeds = []
        self.seed_path = seed_path
        self.connection = connection
        self.seed_module = seed_path.replace("/", ".").replace("\\", ".")

    async def call(self, *seeder_classes):
        for seeder_class in seeder_classes:
            self.ran_seeds.append(seeder_class)
            await seeder_class(connection=self.connection).run()

    async def run_database_seed(self):
        database_seeder = pydoc.locate(f"{self.seed_module}.database_seeder.DatabaseSeeder")

        if not database_seeder:
            raise ValueError(f"Could not find the DatabaseSeeder class in {self.seed_module}.database_seeder")

        self.ran_seeds.append(database_seeder)

        await database_seeder(connection=self.connection).run()

    async def run_specific_seed(self, seed):
        file_name = f"{self.seed_module}.{seed}"
        database_seeder = pydoc.locate(file_name)

        if not database_seeder:
            raise ValueError(f"Could not find the {file_name} seeder file")

        self.ran_seeds.append(database_seeder)

        await database_seeder(connection=self.connection).run()

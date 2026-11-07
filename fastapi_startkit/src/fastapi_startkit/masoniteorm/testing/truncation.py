from typing import TYPE_CHECKING, Any, ClassVar, cast

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class DatabaseTruncation:
    migrated: ClassVar[bool] = False

    tables_to_truncate: ClassVar[list[str] | None] = None
    except_tables: ClassVar[list[str]] = []
    connection: ClassVar[str | None] = None
    seed: ClassVar[bool] = True
    seeder: ClassVar[str | None] = None
    migration_directory: ClassVar[str] = "databases/migrations"
    seed_directory: ClassVar[str] = "databases/seeders"

    async def asyncStartTestRun(self):
        await self.truncate_database()

    async def truncate_database(self) -> None:
        if DatabaseTruncation.migrated:
            await self.truncate_tables()
        else:
            await self.migrate_fresh()
            DatabaseTruncation.migrated = True

        if self.seed or self.seeder:
            await self.seed_database()

    async def migrate_fresh(self) -> None:
        from fastapi_startkit.masoniteorm.migrations import Migrator

        migrator = Migrator(
            migration_directory=str(self.application().use_base_path(self.migration_directory)),
            connection=self.connection or "default",
        )
        await migrator.fresh(ignore_fk=True)

    async def truncate_tables(self) -> None:
        from fastapi_startkit.masoniteorm.models import Model

        schema = Model.resolve_db_manager().get_schema_builder()
        if self.connection:
            schema.on(self.connection)
        for table in await self.tables_for_truncation(schema.get_all_tables):
            await schema.truncate(table, foreign_keys=True)

    async def tables_for_truncation(self, all_tables) -> list[str]:
        if self.tables_to_truncate is not None:
            return list(self.tables_to_truncate)

        excluded = {"migrations", *self.except_tables}
        return [table for table in await all_tables() if table not in excluded and not table.startswith("sqlite_")]

    async def seed_database(self) -> None:
        from fastapi_startkit.masoniteorm.commands.DBSeedCommand import DBSeedCommand

        await DBSeedCommand.run_seeders(
            directory=self.seed_directory,
            connection=self.connection or "default",
            class_name=self.seeder,
        )

    @staticmethod
    def application() -> "Application[Any]":
        from fastapi_startkit.application import app

        return cast("Application[Any]", app())

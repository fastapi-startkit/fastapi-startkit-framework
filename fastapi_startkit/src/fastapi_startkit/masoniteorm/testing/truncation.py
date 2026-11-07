from typing import TYPE_CHECKING, Any, ClassVar, cast

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class DatabaseTruncation:
    migrated: ClassVar[set[tuple[str, str]]] = set()

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
        if self.migration_key in DatabaseTruncation.migrated:
            await self.truncate_tables()
        else:
            await self.migrate_fresh()
            DatabaseTruncation.migrated.add(self.migration_key)

        if self.seed or self.seeder:
            await self.seed_database()

    @property
    def migration_key(self) -> tuple[str, str]:
        return (self.connection or "default", self.migration_directory)

    async def migrate_fresh(self) -> None:
        from fastapi_startkit.masoniteorm.migrations import Migrator

        migrator = Migrator(
            migration_directory=str(self.application().use_base_path(self.migration_directory)),
            connection=self.connection or "default",
        )
        await migrator.fresh(ignore_fk=True)

    async def truncate_tables(self) -> None:
        from sqlalchemy import text

        from fastapi_startkit.masoniteorm.models import Model

        schema = Model.resolve_db_manager().get_schema_builder()
        if self.connection:
            schema.on(self.connection)
        tables = await self.tables_for_truncation(schema.get_all_tables)
        if not tables:
            return

        async with schema.get_connection().engine.connect() as connection:
            for statement in self.truncate_statements(schema.platform(), tables):
                await connection.execute(text(statement))
                await connection.commit()

    @staticmethod
    def truncate_statements(platform, tables: list[str]) -> list[str]:
        from fastapi_startkit.masoniteorm.schema.platforms import PostgresPlatform

        if isinstance(platform, PostgresPlatform):
            return [f"TRUNCATE {', '.join(platform.wrap_table(table) for table in tables)} RESTART IDENTITY CASCADE"]

        statements = []
        for table in tables:
            sql = platform.compile_truncate(table, foreign_keys=True)
            statements.extend(sql if isinstance(sql, list) else [sql])
        return statements

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

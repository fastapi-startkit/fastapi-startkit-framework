import asyncio

from cleo.helpers import argument, option

from fastapi_startkit.console import Command
from fastapi_startkit.masoniteorm.schema.Column import Column
from fastapi_startkit.masoniteorm.schema.schema import Schema


class MakeModelDocstringCommand(Command):
    name = "model:docstring"
    description = "Generate model docstring and type hints (for auto-completion)."

    arguments = [
        argument(
            "table",
            description="The table you want to generate docstring and type hints",
        )
    ]

    options = [
        option(
            "type-hints",
            "t",
            description="Also generate type hints for the model attributes",
            flag=True,
        ),
        option(
            "connection",
            "c",
            flag=False,
            default="default",
            description="The connection you want to use",
        ),
    ]

    def handle(self) -> int:
        return asyncio.run(self.handle_async())

    async def handle_async(self) -> int:
        table = self.argument("table")
        schema: Schema = self.container.make("db").get_schema_builder().on(self.option("connection"))

        if not await schema.has_table(table):
            self.line_error(f"There is no such table {table} for this connection.")
            return 1

        columns = await self.get_columns(schema, table)

        self.info(f"Model Docstring for table: {table}")
        self.line('"""')
        for column in columns.values():
            length = f"({column.length})" if column.length else ""
            default = f" default: {column.default}" if column.default is not None else ""
            self.line(f"{column.name}: {column.column_type}{length}{default}")
        self.line('"""')

        if self.option("type-hints"):
            self.info(f"Model Type Hints for table: {table}")
            for name, column in columns.items():
                self.line(f"    {name}: {column.column_python_type.__name__}")

        return 0

    @staticmethod
    async def get_columns(schema: Schema, table: str) -> dict[str, Column]:
        current = await schema.platform().get_current_schema(schema.get_connection(), table)
        return current.get_added_columns()

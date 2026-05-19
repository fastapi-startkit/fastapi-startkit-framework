from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint
from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff


class Schema:
    _type_hints_map = {
        "string": str,
        "char": str,
        "big_increments": int,
        "integer": int,
        "big_integer": int,
        "tiny_integer": int,
        "small_integer": int,
        "medium_integer": int,
        "integer_unsigned": int,
        "big_integer_unsigned": int,
        "tiny_integer_unsigned": int,
        "small_integer_unsigned": int,
        "medium_integer_unsigned": int,
        "increments": int,
        "uuid": str,
        "binary": bytes,
        "boolean": bool,
        "decimal": float,
        "double": float,
        "enum": str,
        "text": str,
        "tiny_text": str,
        "float": float,
        "geometry": str,
        "json": dict,
        "jsonb": bytes,
        "inet": str,
        "cidr": str,
        "macaddr": str,
        "long_text": str,
        "point": str,
        "time": str,
        "timestamp": str,
        "date": str,
        "year": str,
        "datetime": str,
        "tiny_increments": int,
        "unsigned": int,
        "unsigned_integer": int,
    }

    def __init__(self, manager) -> None:
        self._manager = manager
        self._connection = None

    def on(self, connection_name: str) -> "Schema":
        """Select which connection to use.  Returns self for chaining."""
        self._connection = self._manager.connection(connection_name)
        return self

    def get_connection(self):
        if self._connection is None:
            self._connection = self._manager.connection(None)

        return self._connection

    def platform(self):
        return self.get_connection().get_default_platform()()

    async def create(self, table: str) -> Blueprint:
        """Return a Blueprint for a new table (async context manager)."""
        connection = self.get_connection()

        return Blueprint(
            grammar=connection.get_query_grammar(),
            connection=connection,
            table=Table(table),
            action="create",
            platform=connection.get_default_platform(),
        )

    async def create_table_if_not_exists(self, table: str) -> Blueprint:
        if self._connection is None:
            self._connection = self._manager.connection(None)

        return Blueprint(
            grammar=self._connection.get_query_grammar(),
            connection=self._connection,
            table=Table(table),
            action="create_table_if_not_exists",
            platform=self._connection.get_default_platform(),
        )

    async def table(self, table: str) -> Blueprint:
        """Return a Blueprint for altering an existing table (async context manager)."""
        if self._connection is None:
            self._connection = self._manager.connection(None)

        return Blueprint(
            grammar=self._connection.get_query_grammar(),
            connection=self._connection,
            table=TableDiff(table),
            action="alter",
            platform=self._connection.get_default_platform(),
        )

    async def drop_table(self, table: str) -> None:
        sql = self.platform().compile_drop_table(table)
        await self.get_connection().statement(sql, ())

    def drop(self, *args, **kwargs):
        return self.drop_table(*args, **kwargs)

    async def drop_table_if_exists(self, table: str) -> None:
        if self._connection is None:
            self._connection = self._manager.connection(None)

        sql = self._connection.get_default_platform()().compile_drop_table_if_exists(table)
        await self._connection.statement(sql, ())

    async def has_table(self, table: str) -> bool:
        if self._connection is None:
            self._connection = self._manager.connection(None)

        sql = self._connection.get_default_platform()().compile_table_exists(table)
        result = await self._connection.run(sql, ())
        return bool(result.fetchall())

    async def rename(self, table: str, new_name: str) -> None:
        if self._connection is None:
            self._connection = self._manager.connection(None)

        sql = self._connection.get_default_platform()().compile_rename_table(table, new_name)
        await self._connection.run(sql, ())

    async def truncate(self, table: str, foreign_keys: bool = False) -> None:
        connection = self.get_connection()
        sql = self.platform().compile_truncate(table, foreign_keys=foreign_keys)
        if isinstance(sql, list):
            for q in sql:
                await connection.statement(q, ())
        else:
            await connection.statement(sql, ())

    async def has_column(self, table: str, column: str) -> bool:
        connection = self.get_connection()
        sql = self.platform().compile_column_exists(table, column)
        result = await connection.select(sql, ())
        return bool(result)

    async def disable_foreign_key_constraints(self) -> None:
        connection = self.get_connection()
        sql = connection.get_default_platform()().disable_foreign_key_constraints()
        await connection.statement(sql, ())

    async def enable_foreign_key_constraints(self) -> None:
        connection = self.get_connection()
        sql = connection.get_default_platform()().enable_foreign_key_constraints()
        await connection.statement(sql, ())

    async def get_all_tables(self):
        """Gets all tables in the database."""
        connection = self.get_connection()
        platform = connection.get_default_platform()()
        sql = platform.compile_get_all_tables(
            database=connection.config.get("database"),
            schema=connection.config.get("schema"),
        )
        result = await connection.select(sql, ())
        return [list(row.values())[0] for row in result] if result else []

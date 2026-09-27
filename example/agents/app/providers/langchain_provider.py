from fastapi_startkit.support import Provider
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool


class LazyCheckpointer:
    def __init__(self, uri: str):
        self.pool = AsyncConnectionPool[AsyncConnection[DictRow]](
            conninfo=uri,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        self.saver: AsyncPostgresSaver | None = None

    async def resolve(self) -> AsyncPostgresSaver:
        if self.saver is None:
            await self.pool.open()
            saver = AsyncPostgresSaver(self.pool)
            await saver.setup()
            self.saver = saver
        return self.saver

    def __await__(self):
        return self.resolve().__await__()


class LangChainProvider(Provider):
    DB_URI = "postgresql://postgres:postgres@localhost:5432/agents?sslmode=disable"

    def boot(self):
        self.app.bind("checkpointer", LazyCheckpointer(self.DB_URI))

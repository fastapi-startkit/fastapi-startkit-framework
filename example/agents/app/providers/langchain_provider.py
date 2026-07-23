from fastapi_startkit.support import Provider
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class LazyCheckpointer:
    """An awaitable, lazily-initialised async Postgres checkpointer.

    ``Provider.boot()`` runs synchronously while the application is being
    constructed — before any serving event loop exists. Async Postgres
    connections are bound to the event loop that opens them, so the pool
    cannot be opened at boot time. Instead we build the pool closed and open
    it (and run ``setup()``) on first ``await`` inside the request loop,
    caching the ready saver for subsequent calls.

    Usage: ``checkpointer = await app().make("checkpointer")``
    """

    def __init__(self, uri: str):
        self._pool = AsyncConnectionPool(
            conninfo=uri,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        self._saver: AsyncPostgresSaver | None = None

    async def resolve(self) -> AsyncPostgresSaver:
        if self._saver is None:
            await self._pool.open()
            saver = AsyncPostgresSaver(self._pool)
            await saver.setup()
            self._saver = saver
        return self._saver

    def __await__(self):
        return self.resolve().__await__()


class LangChainProvider(Provider):
    DB_URI = "postgresql://postgres:postgres@localhost:5432/agents?sslmode=disable"

    def boot(self):
        self.app.bind("checkpointer", LazyCheckpointer(self.DB_URI))

from fastapi_startkit.fastapi.testing import HttpTestCase


class TestCase(HttpTestCase):
    def get_application(self):
        from bootstrap.application import app

        return app

    async def asyncSetUp(self):
        # Each test runs in a fresh event loop, but the ORM caches engines whose
        # asyncpg connections are bound to the loop that created them. Drop the
        # cache so this test's loop builds its own engine.
        from fastapi_startkit.masoniteorm.models import Model

        for connection in list(Model.db_manager.connections.values()):
            try:
                await connection.engine.dispose()
            except Exception:  # noqa: BLE001 - engine belonged to a dead loop
                pass
        Model.db_manager.connections.clear()

        await super().asyncSetUp()

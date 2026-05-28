from unittest import IsolatedAsyncioTestCase

from fastapi_startkit.masoniteorm import Model

from .fixtures.db import DB


class TestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._prev_db_manager = Model.db_manager
        Model.db_manager = DB

    async def asyncTearDown(self):
        await DB.clear()
        Model.db_manager = self._prev_db_manager

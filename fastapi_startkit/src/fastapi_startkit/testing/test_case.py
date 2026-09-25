import pytest
from abc import abstractmethod
from typing import TYPE_CHECKING
from unittest import IsolatedAsyncioTestCase

if TYPE_CHECKING:
    from fastapi_startkit import Application


class TestCase(IsolatedAsyncioTestCase):
    @pytest.fixture(scope="session", autouse=True)
    async def app(self):
        self.application = self.get_application()

    def setUp(self):
        start_test_run = getattr(self, "startTestRun", None)
        if start_test_run is not None:
            start_test_run()

    def tearDown(self):
        stop_test_run = getattr(self, "stopTestRun", None)
        if stop_test_run is not None:
            stop_test_run()

    async def asyncSetUp(self):
        async_start_test_run = getattr(self, "asyncStartTestRun", None)
        if async_start_test_run is not None:
            await async_start_test_run()

    async def asyncTearDown(self):
        async_stop_test_run = getattr(self, "asyncStopTestRun", None)
        if async_stop_test_run is not None:
            await async_stop_test_run()

    @abstractmethod
    def get_application(self) -> "Application": ...

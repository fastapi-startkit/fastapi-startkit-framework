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
        if hasattr(self, "startTestRun"):
            self.startTestRun()

    def tearDown(self):
        if hasattr(self, "stopTestRun"):
            self.stopTestRun()

    async def asyncSetUp(self):
        if hasattr(self, "asyncStartTestRun"):
            await self.asyncStartTestRun()

    async def asyncTearDown(self):
        if hasattr(self, "asyncStopTestRun"):
            await self.asyncStopTestRun()

    @abstractmethod
    def get_application(self) -> "Application": ...

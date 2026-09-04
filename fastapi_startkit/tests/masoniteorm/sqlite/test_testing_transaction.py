from fastapi_startkit.masoniteorm.testing.transaction import DatabaseTransaction

from ..fixtures.model import User
from .test_case import TestCase


class TestDatabaseTransactionHarness(TestCase):
    async def test_start_and_stop_roll_back_writes(self):
        harness = DatabaseTransaction()
        await harness.asyncStartTestRun()
        try:
            await User.create({"email": "harness@example.com", "name": "Harness", "is_admin": False})
            assert await User.where("email", "harness@example.com").first() is not None
        finally:
            await harness.asyncStopTestRun()
        assert await User.where("email", "harness@example.com").first() is None

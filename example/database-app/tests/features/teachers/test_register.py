from fastapi_startkit.masoniteorm.testing import RefreshDatabase, DatabaseTransaction

from app.models.user import User
from tests.test_case import TestCase


class TestRegister(RefreshDatabase, TestCase):
    async def test_register(self):
        user = User(
            name="Teacher",
            email="teacher@example.com",
            password="password123",
            role="teacher",
        )
        await user.save()

        found = await User.where("email", "teacher@example.com").first()
        assert found is not None
        assert found.role == "teacher"


class TestTableIsClean(DatabaseTransaction, TestCase):
    async def test_table_is_clean(self):
        users = await User.all()
        assert len(users) == 0

from ...fixtures.model import User
from ..test_case import TestCase


class TestQueryBuilderExists(TestCase):
    async def test_exists_returns_true_when_record_matches(self):
        # seeder creates "admin@admin.com" — should be found
        result = await User.query().where("email", "admin@admin.com").exists()
        self.assertTrue(result)

    async def test_exists_returns_false_when_no_match(self):
        result = await User.query().where("email", "nobody@nowhere.com").exists()
        self.assertFalse(result)

    async def test_exists_true_with_no_where_clause(self):
        # The table has seeded rows, so a bare exists() should be True
        result = await User.query().exists()
        self.assertTrue(result)

    async def test_exists_false_on_empty_table(self):
        # Wipe all users then confirm exists() is False
        await User.query().delete()
        result = await User.query().exists()
        self.assertFalse(result)

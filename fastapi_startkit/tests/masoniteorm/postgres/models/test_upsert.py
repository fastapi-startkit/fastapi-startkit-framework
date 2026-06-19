from ..test_case import TestCase
from ...fixtures.model import User


class TestPostgresUpsert(TestCase):
    async def test_upsert_inserts_new_records(self):
        affected = await User.upsert(
            [
                {"email": "u1@example.com", "name": "U1", "is_admin": False},
                {"email": "u2@example.com", "name": "U2", "is_admin": True},
            ],
            unique_by="email",
        )
        self.assertGreaterEqual(affected, 1)

        u1 = await User.where("email", "u1@example.com").first()
        u2 = await User.where("email", "u2@example.com").first()
        self.assertEqual(u1.name, "U1")
        self.assertEqual(u2.name, "U2")
        self.assertTrue(u2.is_admin)

    async def test_upsert_updates_existing_on_conflict(self):
        await User.upsert({"email": "dup@example.com", "name": "Original", "is_admin": False}, unique_by="email")
        await User.upsert({"email": "dup@example.com", "name": "Updated", "is_admin": True}, unique_by="email")

        rows = await User.where("email", "dup@example.com").get()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.first().name, "Updated")
        self.assertTrue(rows.first().is_admin)

    async def test_upsert_respects_update_subset(self):
        await User.upsert({"email": "sub@example.com", "name": "Keep", "is_admin": False}, unique_by="email")
        await User.upsert(
            {"email": "sub@example.com", "name": "Ignored", "is_admin": True},
            unique_by="email",
            update=["is_admin"],
        )

        user = await User.where("email", "sub@example.com").first()
        self.assertEqual(user.name, "Keep")
        self.assertTrue(user.is_admin)

    async def test_upsert_refreshes_updated_at_on_update_branch(self):
        await User.upsert(
            {"email": "ts@example.com", "name": "TS", "is_admin": False, "updated_at": "2000-01-01 00:00:00"},
            unique_by="email",
        )
        before = await User.where("email", "ts@example.com").first()
        self.assertEqual(before.updated_at.year, 2000)

        await User.upsert({"email": "ts@example.com", "name": "TS2", "is_admin": False}, unique_by="email")
        after = await User.where("email", "ts@example.com").first()
        self.assertEqual(after.name, "TS2")
        self.assertNotEqual(after.updated_at.year, 2000)

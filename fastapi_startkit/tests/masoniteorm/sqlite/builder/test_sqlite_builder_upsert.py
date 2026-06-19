from ...fixtures.model import User
from ..test_case import TestCase


class TestQueryBuilderUpsert(TestCase):
    async def test_upsert_inserts_new_rows(self):
        await User.query().upsert(
            [
                {"email": "new1@test.com", "name": "New One", "is_admin": False},
                {"email": "new2@test.com", "name": "New Two", "is_admin": False},
            ],
            unique_by=["email"],
        )

        one = await User.where("email", "new1@test.com").first()
        two = await User.where("email", "new2@test.com").first()
        assert one.name == "New One"
        assert two.name == "New Two"

    async def test_upsert_accepts_a_single_dict(self):
        await User.query().upsert(
            {"email": "solo@test.com", "name": "Solo", "is_admin": False},
            unique_by="email",
        )

        user = await User.where("email", "solo@test.com").first()
        assert user.name == "Solo"

    async def test_upsert_updates_on_conflict_without_duplicating(self):
        await User.query().upsert(
            {"email": "admin@admin.com", "name": "Renamed Admin", "is_admin": True},
            unique_by="email",
        )

        matches = await User.where("email", "admin@admin.com").get()
        assert len(matches) == 1
        assert matches.first().name == "Renamed Admin"

    async def test_upsert_only_updates_listed_columns(self):
        await User.query().upsert(
            {"email": "admin@admin.com", "name": "Partial Update", "is_admin": False},
            unique_by="email",
            update=["name"],
        )

        user = await User.where("email", "admin@admin.com").first()
        assert user.name == "Partial Update"
        # is_admin was excluded from `update`, so the seeded True is preserved.
        assert user.is_admin is True

    async def test_upsert_without_update_list_updates_all_non_unique_columns(self):
        await User.query().upsert(
            {"email": "admin@admin.com", "name": "Full Update", "is_admin": False},
            unique_by="email",
        )

        user = await User.where("email", "admin@admin.com").first()
        assert user.name == "Full Update"
        assert user.is_admin is False

    async def test_upsert_mixes_insert_and_update_in_one_call(self):
        await User.upsert(
            [
                {"email": "admin@admin.com", "name": "Existing Updated", "is_admin": True},
                {"email": "fresh@test.com", "name": "Fresh Insert", "is_admin": False},
            ],
            unique_by="email",
            update=["name"],
        )

        existing = await User.where("email", "admin@admin.com").first()
        fresh = await User.where("email", "fresh@test.com").first()
        assert existing.name == "Existing Updated"
        assert fresh.name == "Fresh Insert"

    async def test_upsert_returns_zero_for_empty_values(self):
        assert await User.query().upsert([], unique_by="email") == 0

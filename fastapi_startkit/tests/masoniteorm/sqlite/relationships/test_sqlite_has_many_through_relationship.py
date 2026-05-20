from fastapi_startkit.masoniteorm.collection import Collection

from ...fixtures.model import Logo, User
from ..test_case import TestCase


class TestHasManyThroughRelationship(TestCase):
    async def test_has_many_through_can_eager_load(self):
        users = await User.where("email", "admin@admin.com").with_("logos").get()
        logos = users.first().logos

        assert isinstance(logos, Collection)
        assert logos.count() == 1
        assert isinstance(logos.first(), Logo)

        # check .first() and .get() produce the same result
        single = await User.where("email", "admin@admin.com").with_("logos").first()
        single_get = await User.where("email", "admin@admin.com").with_("logos").get()

        assert isinstance(single.logos, Collection)
        assert single.logos.count() == single_get.first().logos.count()

    async def test_has_many_through_eager_load_can_be_empty(self):
        users = await User.where("email", "guest@guest.com").with_("logos").get()

        logos = users.first().logos
        assert logos is None

    async def test_has_many_through_can_get_related(self):
        user = await User.where("email", "admin@admin.com").first()
        logos = await user.logos

        assert isinstance(logos, Collection)
        assert isinstance(logos.first(), Logo)
        assert logos.count() == 1

    async def test_has_many_through_has_query(self):
        users = await User.where_has("logos", lambda query: query).get()
        assert users.count() == 1

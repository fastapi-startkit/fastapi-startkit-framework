from ...fixtures.model import Profile
from ...fixtures.model import User
from ..test_case import TestCase


class TestRelationships(TestCase):
    async def test_can_access_relationship(self):
        for user in await User.where("id", 1).get():
            await user.load("profile")
            profile = user.profile
            self.assertIsInstance(profile, Profile)

    async def test_can_access_has_many_relationship(self):
        user = await User.where("email", "admin@admin.com").first()
        await user.load("articles")
        articles = user.articles
        self.assertEqual(len(articles), 1)

    async def test_can_access_relationship_multiple_times(self):
        user = await User.where("id", 1).first()
        await user.load("articles")
        articles = user.articles
        self.assertEqual(len(articles), 1)
        await user.load("articles")
        articles = user.articles
        self.assertEqual(len(articles), 1)

    async def test_can_access_relationship_date(self):
        user = await User.with_("articles").where("email", "admin@admin.com").first()
        for article in user.articles:
            await article.load("logo")
            logo = article.logo
            self.assertTrue(logo.published_date)

    async def test_loading(self):
        users = await User.with_("articles").get()
        for user in users:
            user

    async def test_loading_with_nested_with(self):
        users = await User.with_("articles", "articles.logo").get()
        for user in users:
            for article in user.articles:
                article.logo

    async def test_casting(self):
        users = await User.with_("articles").where("is_admin", True).get()
        for user in users:
            user

    async def test_setting(self):
        users = await User.with_("articles").where("is_admin", True).get()
        for user in users:
            user.name = "Joe"
            user.is_admin = 1
            await user.save()

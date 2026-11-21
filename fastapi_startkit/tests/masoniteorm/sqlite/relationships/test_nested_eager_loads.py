from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.query.EagerRelation import EagerRelations
from fastapi_startkit.masoniteorm.relationships import BelongsTo, HasMany, HasOne
from ..test_case import TestCase


class NestedUser(Model):
    __table__ = "users"

    articles = HasMany["NestedArticle"](local_key="id", foreign_key="user_id")
    profile = HasOne["NestedProfile"](foreign_key="user_id", local_key="id")


class NestedProfile(Model):
    __table__ = "profiles"
    __timestamps__ = False

    user = BelongsTo["NestedUser"](local_key="user_id", foreign_key="id")


class NestedArticle(Model):
    __table__ = "articles"
    __timestamps__ = None

    author = BelongsTo["NestedUser"](local_key="user_id", foreign_key="id")
    logo = HasOne["NestedLogo"](foreign_key="article_id", local_key="id")


class NestedLogo(Model):
    __table__ = "logos"
    __timestamps__ = None

    article = BelongsTo["NestedArticle"](local_key="article_id", foreign_key="id")


class TestEagerRelationsRegister(TestCase):
    def test_keeps_every_nested_head(self):
        eagers = EagerRelations().register("articles.logo", "profile.user")

        self.assertEqual(eagers.nested_eagers, {"articles": ["logo"], "profile": ["user"]})

    def test_keeps_deeper_levels_as_dotted_paths(self):
        eagers = EagerRelations().register("articles.logo.article", "articles.author")

        self.assertEqual(eagers.nested_eagers, {"articles": ["logo.article", "author"]})


class TestNestedEagerLoads(TestCase):
    async def test_two_nested_paths_with_different_heads_both_load(self):
        user = await NestedUser.with_("articles.logo", "profile.user").where("id", 1).first()

        article = user.articles.first()
        self.assertIsInstance(article.logo, NestedLogo)
        self.assertEqual(user.profile.user.id, user.id)

    async def test_three_level_nested_path_loads_every_level(self):
        user = await NestedUser.with_("articles.logo.article.author").where("id", 1).first()

        logo = user.articles.first().logo
        self.assertEqual(logo.article.id, logo.article_id)
        self.assertEqual(logo.article.author.id, user.id)

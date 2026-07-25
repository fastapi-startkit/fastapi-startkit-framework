from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.relationships import MorphMany
from ...fixtures.model import Like, Product
from ..test_case import TestCase


class ArticleModel(Model):
    __table__ = "articles"
    likes: list[Like] = MorphMany("Like", morph_key="likeable_type", morph_id="likeable_id")


Registry.morph_map({"article": ArticleModel, "product": Product})


class TestMorphManyRelationship(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.article = await ArticleModel.create(
            {
                "title": "Test Article",
                "user_id": 1,
                "published_date": "2024-01-01 00:00:00",
            }
        )

    async def test_morph_many_set_keys_defaults(self):
        rel = MorphMany("Like")
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "record_type")
        self.assertEqual(rel.morph_id, "record_id")

    async def test_morph_many_set_keys_keeps_existing(self):
        rel = MorphMany("Like", morph_key="likeable_type", morph_id="likeable_id")
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")

    async def test_morph_map_returns_registry(self):
        rel = MorphMany("Like", morph_key="likeable_type", morph_id="likeable_id")
        morph_map = rel.morph_map()
        self.assertIn("article", morph_map)
        self.assertIn("product", morph_map)

    async def test_get_record_key_lookup_returns_key(self):
        rel = MorphMany("Like", morph_key="likeable_type", morph_id="likeable_id")
        key = rel.get_record_key_lookup(self.article)
        self.assertEqual(key, "article")

    async def test_apply_query_returns_likes_for_article(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        article = await ArticleModel.where("id", self.article.id).first()
        likes_result = await article.likes
        self.assertEqual(len(likes_result), 1)

    async def test_apply_query_returns_empty_for_article_without_likes(self):
        # Don't create any likes for this article
        article = await ArticleModel.where("id", self.article.id).first()
        likes_result = await article.likes
        self.assertEqual(len(likes_result), 0)

    async def test_eager_load_morph_many(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        articles = await ArticleModel.with_("likes").get()
        article = articles.where("id", self.article.id).first()
        self.assertIsNotNone(article)
        self.assertEqual(len(article.likes), 1)

    async def test_eager_load_morph_many_multiple(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        articles = await ArticleModel.with_("likes").get()
        article = articles.where("id", self.article.id).first()
        self.assertEqual(len(article.likes), 2)

    async def test_get_related_with_single_model(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        rel = ArticleModel.likes
        rel._related_builder = self.article.get_builder()
        rel.polymorphic_builder = Like.query()

        result = rel.get_related(None, self.article)
        likes_result = await result
        self.assertEqual(len(likes_result), 1)

    async def test_get_related_with_collection(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        articles = await ArticleModel.get()
        rel = ArticleModel.likes
        rel._related_builder = self.article.get_builder()
        rel.polymorphic_builder = Like.query()

        result = rel.get_related(None, articles)
        likes_result = await result
        self.assertGreaterEqual(len(likes_result), 1)

    async def test_get_related_with_callback(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        rel = ArticleModel.likes
        rel._related_builder = self.article.get_builder()
        rel.polymorphic_builder = Like.query()

        result = rel.get_related(None, self.article, callback=lambda q: q)
        likes_result = await result
        self.assertEqual(len(likes_result), 1)

    async def test_register_related_adds_relation(self):
        await Like.create({"likeable_type": "article", "likeable_id": self.article.id})
        await Like.create({"likeable_type": "product", "likeable_id": 999})

        all_likes = await Like.get()
        article = await ArticleModel.where("id", self.article.id).first()

        rel = ArticleModel.likes
        rel.register_related("likes", article, all_likes)

        self.assertIn("likes", article._relationships)
        article_likes = article._relationships["likes"]
        # Only likes for this article type are included
        for like in article_likes:
            self.assertEqual(like.likeable_type, "article")

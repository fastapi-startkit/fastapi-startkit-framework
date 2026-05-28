from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.relationships import MorphOne
from ...fixtures.model import Like, Product
from ..test_case import TestCase


def first_like(self):
    return Like


class ArticleModelMorphOne(Model):
    __table__ = "articles"
    first_like = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")


Registry.morph_map({"article_one": ArticleModelMorphOne, "product": Product})


class TestMorphOneRelationship(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.article = await ArticleModelMorphOne.create(
            {
                "title": "Test Article",
                "user_id": 1,
                "published_date": "2024-01-01 00:00:00",
            }
        )

    async def test_morph_one_init_with_function(self):
        rel = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")
        self.assertEqual(rel.fn, first_like)

    async def test_morph_one_init_with_string(self):
        # When a string is passed, it's used as morph_key and second arg as morph_id
        rel = MorphOne("likeable_type", "likeable_id")
        self.assertIsNone(rel.fn)
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")

    async def test_morph_one_set_keys_defaults(self):
        rel = MorphOne(first_like)
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "record_type")
        self.assertEqual(rel.morph_id, "record_id")

    async def test_morph_one_set_keys_keeps_existing(self):
        rel = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")

    async def test_morph_map_uses_registry(self):
        rel = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")
        morph_map = rel.morph_map()
        self.assertIsInstance(morph_map, dict)
        self.assertIn("article_one", morph_map)

    async def test_get_record_key_lookup_returns_key(self):
        rel = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")
        key = rel.get_record_key_lookup(self.article)
        self.assertEqual(key, "article_one")

    async def test_get_record_key_lookup_raises_for_unknown(self):
        rel = MorphOne(first_like, morph_key="likeable_type", morph_id="likeable_id")

        class UnknownModel(Model):
            __table__ = "articles"

        unknown = UnknownModel()
        with self.assertRaises(ValueError):
            rel.get_record_key_lookup(unknown)

    async def test_apply_query_returns_single_like(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        article = await ArticleModelMorphOne.where("id", self.article.id).first()
        result = await article.first_like
        # MorphOne returns a single record (first())
        self.assertIsNotNone(result)
        self.assertIsInstance(result, Like)

    async def test_apply_query_returns_none_when_no_likes(self):
        article = await ArticleModelMorphOne.where("id", self.article.id).first()
        result = await article.first_like
        self.assertIsNone(result)

    async def test_eager_load_morph_one(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        articles = await ArticleModelMorphOne.with_("first_like").get()
        article = articles.where("id", self.article.id).first()
        self.assertIsNotNone(article)
        self.assertIsInstance(article.first_like, Like)

    async def test_get_related_with_single_model(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        rel = ArticleModelMorphOne.first_like
        rel._related_builder = self.article.builder
        rel.polymorphic_builder = first_like(rel)()

        result = rel.get_related(None, self.article)
        like = await result
        self.assertIsNotNone(like)
        self.assertIsInstance(like, Like)

    async def test_get_related_with_collection(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        articles = await ArticleModelMorphOne.get()
        rel = ArticleModelMorphOne.first_like
        rel._related_builder = self.article.builder
        rel.polymorphic_builder = first_like(rel)()

        result = rel.get_related(None, articles)
        # With Collection, returns .get() (a Collection)
        likes_result = await result
        self.assertGreaterEqual(len(likes_result), 1)

    async def test_get_related_with_callback(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        rel = ArticleModelMorphOne.first_like
        rel._related_builder = self.article.builder
        rel.polymorphic_builder = first_like(rel)()

        result = rel.get_related(None, self.article, callback=lambda q: q)
        like = await result
        self.assertIsNotNone(like)

    async def test_register_related_adds_first(self):
        await Like.create({"likeable_type": "article_one", "likeable_id": self.article.id})
        all_likes = await Like.get()
        article = await ArticleModelMorphOne.where("id", self.article.id).first()

        rel = ArticleModelMorphOne.first_like
        rel.register_related("first_like", article, all_likes)

        self.assertIn("first_like", article._relationships)

from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.relationships import MorphToMany
from ...fixtures.model import Articles, Product
from ..test_case import TestCase


def record(self):
    return None


class LikeModelMorphToMany(Model):
    __table__ = "likes"
    record = MorphToMany(record, morph_key="likeable_type", morph_id="likeable_id")


# Register article/product so morph_map resolves them
Registry.morph_map({"article_m2m": Articles, "product_m2m": Product})


class TestMorphToManyRelationship(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.article = await Articles.create(
            {
                "title": "M2M Article",
                "user_id": 1,
                "published_date": "2024-01-01 00:00:00",
            }
        )
        self.product = await Product.create({"name": "M2M Product"})

    async def test_morph_to_many_init_with_function(self):
        rel = MorphToMany(record, morph_key="likeable_type", morph_id="likeable_id")
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")
        self.assertEqual(rel.fn, record)

    async def test_morph_to_many_init_with_string(self):
        rel = MorphToMany("likeable_type", "likeable_id")
        self.assertIsNone(rel.fn)
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")

    async def test_morph_to_many_set_keys_defaults(self):
        rel = MorphToMany(record)
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "record_type")
        self.assertEqual(rel.morph_id, "record_id")

    async def test_morph_to_many_set_keys_keeps_existing(self):
        rel = MorphToMany(record, morph_key="likeable_type", morph_id="likeable_id")
        rel.set_keys(None, None)
        self.assertEqual(rel.morph_key, "likeable_type")
        self.assertEqual(rel.morph_id, "likeable_id")

    async def test_morph_map_uses_registry(self):
        rel = MorphToMany(record, morph_key="likeable_type", morph_id="likeable_id")
        morph_map = rel.morph_map()
        self.assertIsInstance(morph_map, dict)
        self.assertIn("article_m2m", morph_map)
        self.assertIn("product_m2m", morph_map)

    async def test_apply_query_resolves_article(self):

        like = await LikeModelMorphToMany.create({"likeable_type": "article_m2m", "likeable_id": self.article.id})
        like_loaded = await LikeModelMorphToMany.where("id", like.id).first()

        rel = LikeModelMorphToMany.record
        rel.set_keys(LikeModelMorphToMany, rel.fn)
        result = rel.apply_query(like_loaded.builder, like_loaded)
        resolved = await result
        self.assertIsNotNone(resolved)
        self.assertIsInstance(resolved, Articles)

    async def test_apply_query_resolves_product(self):
        like = await LikeModelMorphToMany.create({"likeable_type": "product_m2m", "likeable_id": self.product.id})
        like_loaded = await LikeModelMorphToMany.where("id", like.id).first()

        rel = LikeModelMorphToMany.record
        rel.set_keys(LikeModelMorphToMany, rel.fn)
        result = rel.apply_query(like_loaded.builder, like_loaded)
        resolved = await result
        self.assertIsNotNone(resolved)
        self.assertIsInstance(resolved, Product)

    async def test_get_related_with_collection(self):
        await LikeModelMorphToMany.create({"likeable_type": "article_m2m", "likeable_id": self.article.id})
        await LikeModelMorphToMany.create({"likeable_type": "product_m2m", "likeable_id": self.product.id})

        likes = await LikeModelMorphToMany.get()
        rel = LikeModelMorphToMany.record
        rel.set_keys(LikeModelMorphToMany, rel.fn)

        resolved = await rel.get_related(None, likes)
        self.assertIsInstance(resolved, Collection)
        self.assertGreaterEqual(resolved.count(), 1)

    async def test_get_related_with_single_model_no_match(self):
        like = await LikeModelMorphToMany.create({"likeable_type": "unknown_type", "likeable_id": 999})
        like_loaded = await LikeModelMorphToMany.where("id", like.id).first()

        rel = LikeModelMorphToMany.record
        rel.set_keys(LikeModelMorphToMany, rel.fn)
        result = await rel.get_related(None, like_loaded)
        self.assertIsNone(result)

    async def test_register_related_maps_to_model(self):
        await LikeModelMorphToMany.create({"likeable_type": "article_m2m", "likeable_id": self.article.id})
        await LikeModelMorphToMany.create({"likeable_type": "product_m2m", "likeable_id": self.product.id})

        all_articles = await Articles.get()
        like_article = await LikeModelMorphToMany.where("likeable_type", "article_m2m").first()

        rel = LikeModelMorphToMany.record
        rel.register_related("record", like_article, all_articles)

        self.assertIn("record", like_article._relationships)

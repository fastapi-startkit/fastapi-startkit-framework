from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.exceptions import LazyLoadingViolation
from fastapi_startkit.masoniteorm.relationships import MorphTo
from ...fixtures.model import Articles, Like, Product
from ..test_case import TestCase

Registry.morph_map({"article": Articles, "product": Product})


class StringKeyedTag(Model):
    __table__ = "string_keyed_tags"

    taggable = MorphTo("StringKeyedTag", "taggable_type", "taggable_id")


class TestMorphToRelationship(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.article = await Articles.create(
            {
                "title": "MorphTo Article",
                "user_id": 1,
                "published_date": "2024-01-01 00:00:00",
            }
        )

    async def _like_for(self, likeable_type, likeable_id):
        like = await Like.create({"likeable_type": likeable_type, "likeable_id": likeable_id})
        return await Like.where("id", like.id).first()

    async def test_get_related_with_single_model_resolves_record(self):
        like = await self._like_for("article", self.article.id)

        resolved = await Like.record.get_related(None, like)

        self.assertIsInstance(resolved, Articles)
        self.assertEqual(resolved.id, self.article.id)

    async def test_get_related_with_single_model_unknown_type_returns_none(self):
        like = await self._like_for("unknown_type", 999)

        self.assertIsNone(await Like.record.get_related(None, like))

    async def test_apply_query_unknown_type_raises(self):
        like = await self._like_for("unknown_type", 999)

        with self.assertRaisesRegex(ValueError, "unknown_type"):
            Like.record.apply_query(None, like)

    async def test_unloaded_morph_to_raises_lazy_loading_violation(self):
        like = await self._like_for("article", self.article.id)

        with self.assertRaisesRegex(LazyLoadingViolation, "record"):
            like.record


class TestRegistryGetMorphModel(TestCase):
    def test_returns_mapped_model(self):
        self.assertIs(Registry.get_morph_model("article"), Articles)

    def test_raises_for_unmapped_name(self):
        with self.assertRaisesRegex(ValueError, "not_mapped"):
            Registry.get_morph_model("not_mapped")


class TestMorphToEagerLoadSharedIds(TestCase):
    async def test_eager_load_matches_type_and_id_when_ids_collide(self):
        article = await Articles.first()
        product = await Product.first()
        self.assertEqual(article.id, product.id)

        likes = await Like.with_("record").get()

        self.assertEqual(
            sorted((like.likeable_type, type(like.record).__name__, like.record.id) for like in likes),
            [("article", "Articles", article.id), ("product", "Product", product.id)],
        )


class TestMorphToStringMorphIds(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("string_keyed_tags") as table:
            table.id()
            table.string("taggable_type").nullable()
            table.string("taggable_id").nullable()
            table.timestamps()

    async def test_eager_load_matches_string_morph_ids_across_types(self):
        article = await Articles.first()
        product = await Product.first()
        self.assertEqual(article.id, product.id)
        await StringKeyedTag.create({"taggable_type": "product", "taggable_id": str(product.id)})
        await StringKeyedTag.create({"taggable_type": "article", "taggable_id": str(article.id)})

        tags = await StringKeyedTag.with_("taggable").get()

        self.assertEqual(
            sorted((tag.taggable_type, type(tag.taggable).__name__, tag.taggable.id) for tag in tags),
            [("article", "Articles", article.id), ("product", "Product", product.id)],
        )

    async def test_eager_load_leaves_relation_empty_for_null_morph_columns(self):
        article = await Articles.first()
        await StringKeyedTag.create({"taggable_type": "article", "taggable_id": str(article.id)})
        await StringKeyedTag.create({"taggable_type": None, "taggable_id": None})
        await StringKeyedTag.create({"taggable_type": "article", "taggable_id": None})
        await StringKeyedTag.create({"taggable_type": None, "taggable_id": str(article.id)})

        tags = await StringKeyedTag.with_("taggable").order_by("id").get()

        self.assertEqual(
            [type(tag.taggable).__name__ for tag in tags], ["Articles", "NoneType", "NoneType", "NoneType"]
        )

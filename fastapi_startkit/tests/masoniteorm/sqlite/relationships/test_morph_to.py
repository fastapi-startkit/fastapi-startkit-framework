from fastapi_startkit.masoniteorm.models.registry import Registry
from ...fixtures.model import Articles, Like, Product
from ..test_case import TestCase

Registry.morph_map({"article": Articles, "product": Product})


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


class TestRegistryGetMorphModel(TestCase):
    def test_returns_mapped_model(self):
        self.assertIs(Registry.get_morph_model("article"), Articles)

    def test_raises_for_unmapped_name(self):
        with self.assertRaisesRegex(ValueError, "not_mapped"):
            Registry.get_morph_model("not_mapped")

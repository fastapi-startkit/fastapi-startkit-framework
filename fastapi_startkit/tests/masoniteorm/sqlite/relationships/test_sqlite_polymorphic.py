from fastapi_startkit.masoniteorm.models.registry import Registry
from ...fixtures.model import Articles, Like, Product
from ..test_case import TestCase

Registry.morph_map({"article": Articles, "product": Product})


class TestRelationships(TestCase):
    async def test_can_get_polymorphic_relation(self):
        likes = await Like.get()
        for like in likes:
            record = await like.record
            assert isinstance(record, (Articles, Product))

    async def test_can_get_eager_load_polymorphic_relation(self):
        likes = await Like.with_("record").get()
        for like in likes:
            assert isinstance(like.record, (Articles, Product))

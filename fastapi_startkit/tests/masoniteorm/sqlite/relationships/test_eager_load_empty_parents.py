from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.relationships import MorphMany, MorphOne, MorphTo, MorphToMany

from ...fixtures.model import Articles, IncomingShipment, Like, Store, User
from ..test_case import TestCase


def morphed_record(self):
    return Like


class EmptyParentArticle(Model):
    __table__ = "articles"

    likes = MorphMany("Like", morph_key="likeable_type", morph_id="likeable_id")
    first_like = MorphOne(morphed_record, morph_key="likeable_type", morph_id="likeable_id")


class EmptyParentLike(Model):
    __table__ = "likes"

    record = MorphTo("EmptyParentLike", "likeable_type", "likeable_id")
    records = MorphToMany("likeable_type", "likeable_id")


CASES = [
    (EmptyParentArticle, "likes"),
    (EmptyParentArticle, "first_like"),
    (EmptyParentLike, "record"),
    (EmptyParentLike, "records"),
    (Articles, "logo"),
    (User, "profile"),
    (User, "articles"),
    (User, "logos"),
    (Store, "products"),
    (IncomingShipment, "from_country"),
]


class TestEagerLoadEmptyParents(TestCase):
    async def test_with_on_an_empty_parent_set_returns_an_empty_collection(self):
        for model, relation in CASES:
            with self.subTest(model=model.__name__, relation=relation):
                results = await model.with_(relation).where_raw("1 = 0").get()

                assert results.is_empty()

    async def test_first_with_on_an_empty_parent_set_returns_none(self):
        for model, relation in CASES:
            with self.subTest(model=model.__name__, relation=relation):
                assert await model.with_(relation).where_raw("1 = 0").first() is None

from fastapi_startkit.masoniteorm import BelongsTo, Model

from ...fixtures.typed.owners import TypedUser
from ..test_case import TestCase


class Review(Model):
    __table__ = "reviews"
    __timestamps__ = False

    user = BelongsTo["TypedUser"]("TypedUser", "user_id", "id")


class TestBelongsToNullForeignKey(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("reviews") as table:
            table.increments("id")
            table.string("body")
            table.integer("user_id").nullable()

        self.orphan = await Review.create({"body": "orphan", "user_id": None})

    async def test_eager_load_first_with_only_null_foreign_keys_is_none(self):
        review = await Review.with_("user").where("id", self.orphan.id).first_or_fail()

        assert review.user is None

    async def test_eager_load_get_with_only_null_foreign_keys_is_none(self):
        reviews = await Review.with_("user").where("id", self.orphan.id).get()

        assert reviews[0].user is None

    async def test_model_load_with_only_null_foreign_keys_is_none(self):
        review = await Review.where("id", self.orphan.id).first_or_fail()
        await review.load("user")

        assert review.user is None

    async def test_collection_load_with_only_null_foreign_keys_is_none(self):
        reviews = await Review.where("id", self.orphan.id).get()
        await reviews.load("user")

        assert reviews[0].user is None

    async def test_null_and_resolvable_foreign_keys_load_together(self):
        author = await TypedUser.where("email", "admin@admin.com").first_or_fail()
        owned = await Review.create({"body": "owned", "user_id": author.id})

        reviews = await Review.with_("user").get()
        by_id = {review.id: review for review in reviews}

        assert by_id[self.orphan.id].user is None
        assert isinstance(by_id[owned.id].user, TypedUser)
        assert by_id[owned.id].user.id == author.id

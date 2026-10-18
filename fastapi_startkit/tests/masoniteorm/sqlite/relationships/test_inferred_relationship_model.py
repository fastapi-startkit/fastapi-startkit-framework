from typing import Any, assert_type

import pytest

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, HasOne, Model
from fastapi_startkit.masoniteorm.collection import Collection

from ..test_case import TestCase


class InferredProfile(Model):
    __table__ = "profiles"
    __timestamps__ = False

    user = BelongsTo["InferredUser"](local_key="user_id", foreign_key="id")


class InferredArticle(Model):
    __table__ = "articles"
    __timestamps__ = None


class InferredProduct(Model):
    __table__ = "products"


class InferredUser(Model):
    __table__ = "users"

    profile = HasOne["InferredProfile"](foreign_key="user_id", local_key="id")
    articles = HasMany["InferredArticle"](local_key="id", foreign_key="user_id")
    first_article = HasOne[InferredArticle](foreign_key="user_id", local_key="id")


class InferredStore(Model):
    __table__ = "stores"

    products = BelongsToMany["InferredProduct"](
        local_foreign_key="store_id",
        other_foreign_key="product_id",
        local_owner_key="id",
        other_owner_key="id",
        with_timestamps=True,
    )


class TestInferredRelationshipModel(TestCase):
    async def test_belongs_to_and_has_one_resolve_from_the_subscript(self):
        profile = await InferredProfile.with_("user").first_or_fail()

        assert_type(profile.user, InferredUser | None)
        assert isinstance(profile.user, InferredUser)

        user = await InferredUser.with_("profile").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.profile, InferredProfile | None)
        assert isinstance(user.profile, InferredProfile)

    async def test_has_many_resolves_from_the_subscript(self):
        user = await InferredUser.with_("articles").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.articles, Collection[InferredArticle])
        assert [article.title for article in user.articles] == ["Masonite ORM"]

    async def test_belongs_to_many_resolves_from_the_subscript(self):
        store = await InferredStore.create({"name": "Inferred Store"})
        product = await InferredProduct.create({"name": "Inferred Widget"})
        await InferredStore.products.attach(store, product)

        loaded = await InferredStore.with_("products").where("id", store.id).first_or_fail()

        assert_type(loaded.products, Collection[InferredProduct])
        assert [item.name for item in loaded.products] == ["Inferred Widget"]

    async def test_a_class_subscript_is_used_directly(self):
        user = await InferredUser.with_("first_article").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.first_article, InferredArticle | None)
        assert isinstance(user.first_article, InferredArticle)

    def test_an_explicit_model_argument_wins_over_the_subscript(self):
        with pytest.warns(DeprecationWarning):
            relationship = BelongsTo["InferredProfile"]("InferredUser", local_key="user_id", foreign_key="id")

        assert relationship.related_model() is InferredUser

    def test_passing_the_model_as_an_argument_is_deprecated(self):
        with pytest.warns(DeprecationWarning, match=r"removed in 1\.x") as caught:
            HasOne("InferredProfile", "user_id", "id")

        assert 'HasOne["InferredProfile"](...)' in str(caught[0].message)
        assert caught[0].filename == __file__

    async def test_a_model_argument_without_a_subscript_still_resolves_untyped(self):
        with pytest.warns(DeprecationWarning):

            class LegacyUser(Model):
                __table__ = "users"

                profile = HasOne("InferredProfile", "user_id", "id")

        user = await LegacyUser.with_("profile").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.profile, Any)
        assert isinstance(user.profile, InferredProfile)

    def test_a_relationship_without_a_model_fails_at_class_creation(self):
        with pytest.raises(TypeError, match="Orphan.owner"):

            class Orphan(Model):
                owner = BelongsTo(local_key="owner_id", foreign_key="id")

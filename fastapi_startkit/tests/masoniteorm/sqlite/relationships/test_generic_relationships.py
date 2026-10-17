from typing import Any, assert_type

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, HasOne
from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.exceptions import LazyLoadingViolation

from ...fixtures.typed.owners import TypedStore, TypedUser
from ...fixtures.typed.related import TypedArticle, TypedProduct, TypedProfile
from ..test_case import TestCase


class TestGenericRelationships(TestCase):
    def test_subscript_keeps_the_string_forward_reference(self):
        relationship = BelongsTo["TypedUser"]("TypedUser", local_key="user_id", foreign_key="id")

        assert isinstance(relationship, BelongsTo)
        assert relationship.get_builder().get_table_name() == "users"
        assert relationship.local_key == "user_id"
        assert relationship.foreign_key == "id"

    def test_class_access_is_the_relationship(self):
        assert_type(TypedUser.profile, HasOne[TypedProfile])
        assert_type(TypedUser.articles, HasMany[TypedArticle])
        assert_type(TypedProfile.user, BelongsTo[TypedUser])
        assert_type(TypedStore.products, BelongsToMany[TypedProduct])

        assert isinstance(TypedUser.profile, HasOne)
        assert isinstance(TypedStore.products, BelongsToMany)

    async def test_eager_loaded_single_relationships_are_typed(self):
        user = await TypedUser.with_("profile").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.profile, TypedProfile | None)
        assert isinstance(user.profile, TypedProfile)
        assert user.profile.name == "Joe Profile"

        profile = await TypedProfile.with_("user").first_or_fail()

        assert_type(profile.user, TypedUser | None)
        assert isinstance(profile.user, TypedUser)

    async def test_eager_loaded_many_relationships_are_typed(self):
        users = await TypedUser.with_("articles").where("email", "admin@admin.com").get()
        articles = users[0].articles

        assert_type(articles, Collection[TypedArticle])
        assert [article.title for article in articles] == ["Masonite ORM"]

    async def test_eager_loaded_belongs_to_many_is_typed(self):
        store = await TypedStore.create({"name": "Typed Store"})
        product = await TypedProduct.create({"name": "Typed Widget"})
        await TypedStore.products.attach(store, product)

        loaded = await TypedStore.with_("products").where("id", store.id).first_or_fail()

        assert_type(loaded.products, Collection[TypedProduct])
        assert [item.name for item in loaded.products] == ["Typed Widget"]

    async def test_where_has_uses_subscripted_relationships(self):
        users = await TypedUser.where_has("articles", lambda query: query.where("title", "Masonite ORM")).get()

        assert [user.email for user in users] == ["admin@admin.com"]

    async def test_unsubscripted_relationship_stays_untyped(self):
        user = await TypedUser.with_("untyped_profile").where("email", "admin@admin.com").first_or_fail()

        assert_type(user.untyped_profile, Any)
        assert isinstance(user.untyped_profile, TypedProfile)

    async def test_unloaded_relationship_raises_lazy_loading_violation(self):
        user = await TypedUser.where("email", "admin@admin.com").first_or_fail()

        with self.assertRaises(LazyLoadingViolation) as raised:
            user.profile

        message = str(raised.exception)
        assert "[profile]" in message
        assert "[TypedUser]" in message
        assert 'TypedUser.with_("profile")' in message
        assert 'load("profile")' in message

    async def test_load_eager_loads_onto_the_model(self):
        user = await TypedUser.where("email", "admin@admin.com").first_or_fail()

        loaded = await user.load("profile", "articles")

        assert_type(loaded, TypedUser)
        assert_type(loaded.profile, TypedProfile | None)
        assert isinstance(loaded.profile, TypedProfile)
        assert [article.title for article in loaded.articles] == ["Masonite ORM"]

    async def test_relationships_without_records_are_registered_as_empty(self):
        user = await TypedUser.create({"name": "Lonely", "email": "lonely@example.com"})

        await user.load("profile", "articles")

        assert user.profile is None
        assert user.articles.is_empty()

        eager = await TypedUser.with_("profile", "articles").where("id", user.id).get()

        assert eager[0].profile is None
        assert eager[0].articles.is_empty()

        first = await TypedUser.with_("articles").where("id", user.id).first_or_fail()

        assert first.articles.is_empty()

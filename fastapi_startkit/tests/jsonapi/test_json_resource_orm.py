"""Integration tests for JsonResource with real ORM models.

Uses the SQLite test database (same fixtures as the masoniteorm test suite)
to verify that JsonResource works end-to-end with actual Model instances:
auto-serialization from model.serialize(), hidden fields, collection() with
real query results, and collection() with LengthAwarePaginator / SimplePaginator.
"""

from unittest import IsolatedAsyncioTestCase

from fastapi_startkit.jsonapi import JsonResource, ResourceCollection
from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.testing.transaction import RefreshDatabase

from tests.masoniteorm.sqlite.fixtures.db import DB
from tests.masoniteorm.fixtures.migration import migrate, wipe
from tests.masoniteorm.fixtures.seeder import seeder
from tests.masoniteorm.fixtures.model import User, Articles


# ---------------------------------------------------------------------------
# Resource definitions
# ---------------------------------------------------------------------------


class UserResource(JsonResource[User]):
    """Exposes all User fields except sensitive ones."""

    hidden = ["email_verified_at", "preferences", "address"]


class ArticleResource(JsonResource[Articles]):
    """Exposes Article fields; author relationship via class-reference form.

    The key "author" tells the framework to read ``self.model.author``
    and wrap it automatically with ``UserResource``.
    """

    def to_relationships(self):
        return {"author": UserResource}


# ---------------------------------------------------------------------------
# Test base — mirrors tests/masoniteorm/sqlite/test_case.py
# ---------------------------------------------------------------------------


class OrmTestCase(RefreshDatabase, IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = DB
        Model.db_manager = DB
        self.schema = DB.get_schema_builder()
        await self._reset_db()

    async def asyncTearDown(self):
        await DB.clear()
        await wipe(DB.get_schema_builder())

    @staticmethod
    async def _reset_db():
        await DB.clear()
        schema = DB.get_schema_builder()
        await wipe(schema)
        await migrate(schema)
        await seeder()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJsonResourceWithOrmModel(OrmTestCase):
    """JsonResource auto-serializes directly from a real Model instance."""

    async def test_type_derived_from_class_name(self):
        user = await User.first()
        resource = UserResource(user)
        self.assertEqual(resource.type, "users")

    async def test_id_set_from_model(self):
        user = await User.first()
        resource = UserResource(user)
        self.assertEqual(resource.id, user.id)

    async def test_attributes_come_from_model_serialize(self):
        user = await User.first()
        doc = UserResource(user).serialize()
        attrs = doc["data"]["attributes"]

        # Fields from User.serialize() must appear in attributes
        self.assertIn("name", attrs)
        self.assertIn("email", attrs)
        self.assertIn("is_admin", attrs)

    async def test_hidden_fields_excluded(self):
        user = await User.first()
        doc = UserResource(user).serialize()
        attrs = doc["data"]["attributes"]

        self.assertNotIn("email_verified_at", attrs)
        self.assertNotIn("preferences", attrs)
        self.assertNotIn("address", attrs)

    async def test_non_hidden_fields_present(self):
        user = await User.first()
        doc = UserResource(user).serialize()
        attrs = doc["data"]["attributes"]

        self.assertEqual(attrs["name"], "Joe")
        self.assertEqual(attrs["email"], "admin@admin.com")
        self.assertTrue(attrs["is_admin"])

    async def test_fields_chain_restricts_attributes(self):
        user = await User.first()
        doc = UserResource(user).fields("name").serialize()
        attrs = doc["data"]["attributes"]

        self.assertIn("name", attrs)
        self.assertNotIn("email", attrs)
        self.assertNotIn("is_admin", attrs)

    async def test_data_envelope_shape(self):
        user = await User.first()
        doc = UserResource(user).serialize()

        self.assertIn("data", doc)
        self.assertEqual(doc["data"]["type"], "users")
        self.assertEqual(doc["data"]["id"], str(user.id))
        self.assertIn("attributes", doc["data"])


class TestJsonResourceCollectionWithOrm(OrmTestCase):
    """JsonResource.collection() wraps real ORM query results."""

    async def test_collection_from_all(self):
        users = await User.all()
        doc = UserResource.collection(users).serialize()

        self.assertIsInstance(doc["data"], list)
        self.assertEqual(len(doc["data"]), 2)  # seeder creates 2 users

    async def test_collection_returns_resource_collection(self):
        users = await User.all()
        coll = UserResource.collection(users)
        self.assertIsInstance(coll, ResourceCollection)

    async def test_collection_items_have_correct_type(self):
        users = await User.all()
        doc = UserResource.collection(users).serialize()

        for item in doc["data"]:
            self.assertEqual(item["type"], "users")

    async def test_collection_fields_chain(self):
        users = await User.all()
        doc = UserResource.collection(users).fields("name", "email").serialize()

        for item in doc["data"]:
            self.assertIn("name", item["attributes"])
            self.assertIn("email", item["attributes"])
            self.assertNotIn("is_admin", item["attributes"])

    async def test_no_meta_for_plain_list(self):
        users = await User.all()
        doc = UserResource.collection(users).serialize()
        self.assertNotIn("meta", doc)


class TestJsonResourceWithLengthAwarePaginator(OrmTestCase):
    """collection() with a real LengthAwarePaginator includes pagination meta."""

    async def test_returns_resource_collection(self):
        paginator = await User.query().paginate(1)
        coll = UserResource.collection(paginator)
        self.assertIsInstance(coll, ResourceCollection)

    async def test_data_contains_items(self):
        paginator = await User.query().paginate(1)
        doc = UserResource.collection(paginator).serialize()
        self.assertIsInstance(doc["data"], list)
        self.assertGreater(len(doc["data"]), 0)

    async def test_meta_total_present(self):
        paginator = await User.query().paginate(1)
        doc = UserResource.collection(paginator).serialize()
        self.assertIn("meta", doc)
        self.assertEqual(doc["meta"]["total"], 2)

    async def test_meta_per_page(self):
        paginator = await User.query().paginate(1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["per_page"], 1)

    async def test_meta_current_page(self):
        paginator = await User.query().paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["current_page"], 1)

    async def test_meta_last_page(self):
        paginator = await User.query().paginate(1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["last_page"], 2)  # 2 users, 1 per page

    async def test_meta_next_page(self):
        paginator = await User.query().paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["next_page"], 2)

    async def test_meta_no_next_page_on_last(self):
        paginator = await User.query().paginate(1, 2)  # page 2 of 2
        doc = UserResource.collection(paginator).serialize()
        self.assertIsNone(doc["meta"]["next_page"])

    async def test_fields_chain_on_paginated_collection(self):
        paginator = await User.query().paginate(10)
        doc = UserResource.collection(paginator).fields("name").serialize()
        for item in doc["data"]:
            self.assertIn("name", item["attributes"])
            self.assertNotIn("email", item["attributes"])


class TestJsonResourceWithSimplePaginator(OrmTestCase):
    """collection() with a real SimplePaginator includes pagination meta."""

    async def test_returns_resource_collection(self):
        paginator = await User.query().simple_paginate(1, 1)
        coll = UserResource.collection(paginator)
        self.assertIsInstance(coll, ResourceCollection)

    async def test_meta_present(self):
        paginator = await User.query().simple_paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertIn("meta", doc)

    async def test_meta_current_page(self):
        paginator = await User.query().simple_paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["current_page"], 1)

    async def test_meta_has_next_page(self):
        paginator = await User.query().simple_paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertEqual(doc["meta"]["next_page"], 2)

    async def test_meta_no_total(self):
        # SimplePaginator does not provide total / last_page
        paginator = await User.query().simple_paginate(1, 1)
        doc = UserResource.collection(paginator).serialize()
        self.assertNotIn("total", doc["meta"])
        self.assertNotIn("last_page", doc["meta"])


class TestJsonResourceRelationshipsWithOrm(OrmTestCase):
    """to_relationships() wired to real ORM data via with_()."""

    async def test_relationships_in_data_when_author_set(self):
        article = await Articles.first()
        author = await User.find(article.user_id)

        # Attach author onto model so to_relationships() can access it
        article.author = author
        doc = ArticleResource(article).serialize()

        self.assertIn("relationships", doc["data"])
        self.assertIn("author", doc["data"]["relationships"])

    async def test_include_author_sideloaded(self):
        article = await Articles.first()
        author = await User.find(article.user_id)
        article.author = author

        doc = ArticleResource(article).include("author").serialize()

        self.assertIn("included", doc)
        inc = doc["included"][0]
        self.assertEqual(inc["type"], "users")
        self.assertEqual(inc["id"], str(author.id))

    async def test_include_author_attributes(self):
        article = await Articles.first()
        author = await User.find(article.user_id)
        article.author = author

        doc = ArticleResource(article).include("author").serialize()

        inc_attrs = doc["included"][0]["attributes"]
        self.assertIn("name", inc_attrs)
        self.assertEqual(inc_attrs["name"], "Joe")

    async def test_fields_restrict_included_resource(self):
        article = await Articles.first()
        author = await User.find(article.user_id)
        article.author = author

        doc = ArticleResource(article).include("author").fields("users.name").serialize()

        inc_attrs = doc["included"][0]["attributes"]
        self.assertIn("name", inc_attrs)
        self.assertNotIn("email", inc_attrs)

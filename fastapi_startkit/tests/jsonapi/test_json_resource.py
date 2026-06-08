"""Tests for the new JsonResource[T] generic base class.

Covers:
- Auto-type derivation from class name via inflection
- __init__(self, model) storing self.model and self.id
- Default to_attributes() using model.serialize() minus 'id' and hidden fields
- hidden class var blacklist
- with_() method merging into top-level envelope
- JsonResource.collection() with plain lists and paginators
- Backward-compat aliases: JsonAPIResponse, JsonAPIListResponse
"""

from __future__ import annotations

from fastapi_startkit.jsonapi import (
    JsonAPIListResponse,
    JsonAPIResponse,
    JsonResource,
    _ResourceCollection,
)
from fastapi_startkit.masoniteorm.pagination.LengthAwarePaginator import (
    LengthAwarePaginator,
)
from fastapi_startkit.masoniteorm.pagination.SimplePaginator import SimplePaginator


# ---------------------------------------------------------------------------
# Fake model helpers
# ---------------------------------------------------------------------------


class _FakeModelCollection:
    """Minimal list-like object with a .serialize() method (mimics ORM result)."""

    def __init__(self, rows):
        self._rows = rows

    def serialize(self, *args, **kwargs):
        return [r.__dict__ for r in self._rows]

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, item):
        return self._rows[item]

    def __iter__(self):
        return iter(self._rows)


class FakeModel:
    """Minimal model with id and serialize()."""

    def __init__(self, id_, **fields):
        self.id = id_
        for k, v in fields.items():
            setattr(self, k, v)
        self._fields = {"id": id_, **fields}

    def serialize(self):
        return dict(self._fields)


class FakeModelNoSerialize:
    """Model without a serialize() method."""

    def __init__(self, id_, name):
        self.id = id_
        self.name = name


# ---------------------------------------------------------------------------
# Concrete resource fixtures
# ---------------------------------------------------------------------------


class PostResource(JsonResource[FakeModel]):
    """Auto-type = "posts", auto-attributes from model.serialize()."""

    pass


class UserResource(JsonResource[FakeModel]):
    """hidden fields exclude 'password'."""

    hidden = ["password"]


class ArticleResource(JsonResource[FakeModel]):
    """Injects extra top-level envelope keys via with_()."""

    def with_(self):
        return {"meta": {"version": "1.0"}}


class AgentResource(JsonResource[FakeModel]):
    """Tests multi-word class name -> tableized type."""

    pass


class UserProfileResource(JsonResource[FakeModel]):
    """Multi-word: UserProfile -> user_profiles."""

    pass


# ---------------------------------------------------------------------------
# 1. Auto-type derivation
# ---------------------------------------------------------------------------


class TestAutoType:
    def test_single_word_resource(self):
        model = FakeModel(1, title="Hello")
        resource = PostResource(model)
        assert resource.type == "posts"

    def test_single_word_user(self):
        model = FakeModel(1, name="Alice")
        resource = UserResource(model)
        assert resource.type == "users"

    def test_multi_word_type(self):
        model = FakeModel(1, name="Alice")
        resource = UserProfileResource(model)
        assert resource.type == "user_profiles"

    def test_agent_type(self):
        model = FakeModel(1, name="Bot")
        resource = AgentResource(model)
        assert resource.type == "agents"

    def test_explicit_type_overrides_auto(self):
        class CustomResource(JsonResource[FakeModel]):
            type = "my_custom_type"

        model = FakeModel(1)
        resource = CustomResource(model)
        assert resource.type == "my_custom_type"

    def test_type_not_set_on_base_class(self):
        # JsonResource itself has type="" — auto-type only fires for subclasses
        assert JsonResource.type == ""


# ---------------------------------------------------------------------------
# 2. __init__ stores model and id
# ---------------------------------------------------------------------------


class TestInit:
    def test_model_stored(self):
        model = FakeModel(42, title="Test")
        resource = PostResource(model)
        assert resource.model is model

    def test_id_from_model(self):
        model = FakeModel(99, title="Test")
        resource = PostResource(model)
        assert resource.id == 99

    def test_id_defaults_to_empty_string_when_no_id(self):
        class NoIdModel:
            def serialize(self):
                return {"name": "x"}

        class ThingResource(JsonResource[NoIdModel]):
            pass

        m = NoIdModel()
        r = ThingResource(m)
        assert r.id == ""


# ---------------------------------------------------------------------------
# 3. Default to_attributes() auto-serialization
# ---------------------------------------------------------------------------


class TestToAttributesAutoSerialize:
    def test_attributes_from_serialize(self):
        model = FakeModel(1, title="Hello", body="World")
        resource = PostResource(model)
        attrs = resource.to_attributes()
        assert attrs == {"title": "Hello", "body": "World"}

    def test_id_excluded_from_attributes(self):
        model = FakeModel(1, title="Hello")
        resource = PostResource(model)
        attrs = resource.to_attributes()
        assert "id" not in attrs

    def test_returns_none_when_model_has_no_serialize(self):
        class BareResource(JsonResource[FakeModelNoSerialize]):
            pass

        model = FakeModelNoSerialize(1, "Alice")
        resource = BareResource(model)
        assert resource.to_attributes() is None

    def test_returns_none_when_serialize_returns_only_id(self):
        model = FakeModel(1)  # only 'id' field
        resource = PostResource(model)
        # After stripping 'id', empty dict -> None
        assert resource.to_attributes() is None

    def test_in_serialized_document(self):
        model = FakeModel(1, title="Hello", body="World")
        doc = PostResource(model).serialize()
        assert doc["data"]["attributes"] == {"title": "Hello", "body": "World"}


# ---------------------------------------------------------------------------
# 4. hidden class var
# ---------------------------------------------------------------------------


class TestHidden:
    def test_hidden_field_excluded(self):
        model = FakeModel(1, name="Alice", password="secret")
        resource = UserResource(model)
        attrs = resource.to_attributes()
        assert "password" not in attrs
        assert attrs["name"] == "Alice"

    def test_non_hidden_fields_present(self):
        model = FakeModel(1, name="Alice", email="a@b.com", password="x")
        resource = UserResource(model)
        attrs = resource.to_attributes()
        assert "name" in attrs
        assert "email" in attrs

    def test_multiple_hidden_fields(self):
        class StrictUser(JsonResource[FakeModel]):
            hidden = ["password", "remember_token", "api_key"]

        model = FakeModel(1, name="Bob", password="s", remember_token="t", api_key="k")
        resource = StrictUser(model)
        attrs = resource.to_attributes()
        assert attrs == {"name": "Bob"}

    def test_id_always_hidden_regardless_of_hidden_list(self):
        # 'id' is excluded by default even when hidden=[]
        model = FakeModel(7, title="Hi")
        resource = PostResource(model)
        attrs = resource.to_attributes()
        assert "id" not in attrs


# ---------------------------------------------------------------------------
# 5. with_() merges into top-level envelope
# ---------------------------------------------------------------------------


class TestWith:
    def test_with_adds_top_level_key(self):
        model = FakeModel(1, title="Hi")
        doc = ArticleResource(model).serialize()
        assert "meta" in doc
        assert doc["meta"] == {"version": "1.0"}

    def test_with_overrides_to_meta(self):
        class PriorityResource(JsonResource[FakeModel]):
            def to_meta(self):
                return {"from_to_meta": True}

            def with_(self):
                # with_() is applied after to_meta(), so it wins
                return {"meta": {"from_with_": True}}

        model = FakeModel(1, title="Hi")
        doc = PriorityResource(model).serialize()
        assert doc["meta"] == {"from_with_": True}

    def test_empty_with_does_not_pollute_document(self):
        model = FakeModel(1, title="Hi")
        doc = PostResource(model).serialize()
        # with_() returns {} by default -> no extra keys
        assert set(doc.keys()) == {"data"}

    def test_with_merges_multiple_keys(self):
        class RichResource(JsonResource[FakeModel]):
            def with_(self):
                return {"jsonapi": {"version": "1.1"}, "meta": {"page": 1}}

        model = FakeModel(1, title="Hi")
        doc = RichResource(model).serialize()
        assert doc["jsonapi"] == {"version": "1.1"}
        assert doc["meta"] == {"page": 1}


# ---------------------------------------------------------------------------
# 6. JsonResource.collection() — plain list
# ---------------------------------------------------------------------------


class TestCollectionList:
    def test_returns_resource_collection(self):
        models = [FakeModel(i, title=f"Post {i}") for i in range(3)]
        coll = PostResource.collection(models)
        assert isinstance(coll, _ResourceCollection)

    def test_data_length(self):
        models = [FakeModel(i, title=f"Post {i}") for i in range(5)]
        doc = PostResource.collection(models).serialize()
        assert len(doc["data"]) == 5

    def test_each_item_type(self):
        models = [FakeModel(1, title="A"), FakeModel(2, title="B")]
        doc = PostResource.collection(models).serialize()
        for item in doc["data"]:
            assert item["type"] == "posts"

    def test_empty_list(self):
        doc = PostResource.collection([]).serialize()
        assert doc["data"] == []

    def test_no_meta_for_plain_list(self):
        models = [FakeModel(1, title="A")]
        doc = PostResource.collection(models).serialize()
        assert "meta" not in doc


# ---------------------------------------------------------------------------
# 7. JsonResource.collection() — LengthAwarePaginator
# ---------------------------------------------------------------------------


class TestCollectionLengthAwarePaginator:
    def _make_paginator(self, n=3, per_page=2, page=1, total=10):
        rows = [FakeModel(i, title=f"P{i}") for i in range(1, n + 1)]
        collection = _FakeModelCollection(rows)
        return LengthAwarePaginator(collection, per_page=per_page, current_page=page, total=total)

    def test_returns_resource_collection(self):
        pag = self._make_paginator()
        coll = PostResource.collection(pag)
        assert isinstance(coll, _ResourceCollection)

    def test_items_wrapped(self):
        pag = self._make_paginator(n=3)
        doc = PostResource.collection(pag).serialize()
        assert len(doc["data"]) == 3

    def test_meta_total(self):
        pag = self._make_paginator(n=2, per_page=2, page=1, total=10)
        doc = PostResource.collection(pag).serialize()
        assert "meta" in doc
        assert doc["meta"]["total"] == 10

    def test_meta_current_page(self):
        pag = self._make_paginator(n=2, per_page=2, page=2, total=10)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["current_page"] == 2

    def test_meta_last_page(self):
        pag = self._make_paginator(n=2, per_page=2, page=1, total=10)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["last_page"] == 5  # ceil(10/2)

    def test_meta_next_page(self):
        pag = self._make_paginator(n=2, per_page=2, page=1, total=10)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["next_page"] == 2

    def test_meta_no_next_page_on_last(self):
        pag = self._make_paginator(n=2, per_page=2, page=5, total=10)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["next_page"] is None


# ---------------------------------------------------------------------------
# 8. JsonResource.collection() — SimplePaginator
# ---------------------------------------------------------------------------


class TestCollectionSimplePaginator:
    def _make_paginator(self, n=3, per_page=2, page=1):
        # SimplePaginator needs n+1 to detect has_more
        rows = [FakeModel(i, title=f"P{i}") for i in range(1, n + 2)]
        collection = _FakeModelCollection(rows)
        return SimplePaginator(collection, per_page=per_page, current_page=page)

    def test_returns_resource_collection(self):
        pag = self._make_paginator()
        coll = PostResource.collection(pag)
        assert isinstance(coll, _ResourceCollection)

    def test_meta_present(self):
        pag = self._make_paginator(n=3, per_page=2, page=1)
        doc = PostResource.collection(pag).serialize()
        assert "meta" in doc

    def test_meta_has_next_page(self):
        pag = self._make_paginator(n=3, per_page=2, page=1)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["next_page"] == 2

    def test_meta_current_page(self):
        pag = self._make_paginator(n=3, per_page=2, page=3)
        doc = PostResource.collection(pag).serialize()
        assert doc["meta"]["current_page"] == 3


# ---------------------------------------------------------------------------
# 9. Backward-compat aliases
# ---------------------------------------------------------------------------


class TestBackwardCompatAliases:
    def test_json_api_response_is_json_resource(self):
        assert JsonAPIResponse is JsonResource

    def test_json_api_list_response_is_resource_collection(self):
        assert JsonAPIListResponse is _ResourceCollection

    def test_old_style_subclass_still_works(self):
        """Old-style JsonAPIResponse subclass with custom __init__ must still work."""

        class LegacyUser(JsonAPIResponse):
            type = "users"
            attributes = ["name", "email"]

            def __init__(self, id_, name, email):
                self.id = id_
                self.name = name
                self.email = email

            def to_attributes(self):
                return {"name": self.name, "email": self.email}

        resource = LegacyUser(1, "Alice", "alice@example.com")
        doc = resource.serialize()
        assert doc["data"]["type"] == "users"
        assert doc["data"]["id"] == "1"
        assert doc["data"]["attributes"] == {"name": "Alice", "email": "alice@example.com"}

    def test_old_style_list_response(self):
        """JsonAPIListResponse([...]) still works as before."""

        class LegacyPost(JsonAPIResponse):
            type = "posts"
            attributes = ["title"]

            def __init__(self, id_, title):
                self.id = id_
                self.title = title

            def to_attributes(self):
                return {"title": self.title}

        posts = [LegacyPost(i, f"Title {i}") for i in range(3)]
        doc = JsonAPIListResponse(posts).serialize()
        assert isinstance(doc["data"], list)
        assert len(doc["data"]) == 3

    def test_old_style_explicit_type_not_overridden(self):
        """__init_subclass__ must NOT override an explicit type = "..." class attr."""

        class ThingResource(JsonAPIResponse):
            type = "special_things"

            def __init__(self):
                self.id = 1

        r = ThingResource()
        assert r.type == "special_things"


# ---------------------------------------------------------------------------
# 10. Full serialize() document shape
# ---------------------------------------------------------------------------


class TestSerializeDocumentShape:
    def test_data_type_and_id(self):
        model = FakeModel(42, title="Foo")
        doc = PostResource(model).serialize()
        assert doc["data"]["type"] == "posts"
        assert doc["data"]["id"] == "42"

    def test_no_extra_keys_by_default(self):
        model = FakeModel(1, title="Hi")
        doc = PostResource(model).serialize()
        assert set(doc.keys()) == {"data"}

    def test_links_present_when_overridden(self):
        class LinkedPost(JsonResource[FakeModel]):
            def to_links(self):
                return {"self": f"/api/posts/{self.id}"}

        model = FakeModel(5, title="Hi")
        doc = LinkedPost(model).serialize()
        assert doc["links"] == {"self": "/api/posts/5"}

    def test_meta_present_when_overridden(self):
        class MetaPost(JsonResource[FakeModel]):
            def to_meta(self):
                return {"foo": "bar"}

        model = FakeModel(1, title="Hi")
        doc = MetaPost(model).serialize()
        assert doc["meta"] == {"foo": "bar"}

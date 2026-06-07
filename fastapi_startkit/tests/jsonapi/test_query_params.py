"""Tests for parse_include(), parse_fields(), sparse fieldsets, and
the FastAPI ASGI __call__ integration (return resource directly).
"""

import pytest
from fastapi_startkit.jsonapi import (
    JsonAPIListResponse,
    JsonAPIResponse,
    parse_fields,
    parse_include,
)


# ---------------------------------------------------------------------------
# Fixture resources
# ---------------------------------------------------------------------------

class UserResource(JsonAPIResponse):
    type = "users"
    attributes = ["name", "email", "role"]

    def __init__(self, id_, name, email="u@example.com", role="member"):
        self.id = id_
        self.name = name
        self.email = email
        self.role = role

    def to_attributes(self):
        return {"name": self.name, "email": self.email, "role": self.role}


class PostResource(JsonAPIResponse):
    type = "posts"
    attributes = ["title", "body", "created_at"]

    def __init__(self, id_, title, body="", created_at="2024-01-01", author=None):
        self.id = id_
        self.title = title
        self.body = body
        self.created_at = created_at
        self._author = author

    def to_attributes(self):
        return {"title": self.title, "body": self.body, "created_at": self.created_at}

    def to_relationships(self):
        if self._author is None:
            return None
        return {"author": self._author}


# ---------------------------------------------------------------------------
# parse_include() tests
# ---------------------------------------------------------------------------

class TestParseInclude:
    def test_single_name(self):
        assert parse_include("author") == ["author"]

    def test_multiple_names(self):
        assert parse_include("author,comments") == ["author", "comments"]

    def test_strips_whitespace(self):
        assert parse_include("author, comments , tags") == ["author", "comments", "tags"]

    def test_none_returns_empty(self):
        assert parse_include(None) == []

    def test_empty_string_returns_empty(self):
        assert parse_include("") == []

    def test_drops_empty_segments(self):
        assert parse_include("author,,comments") == ["author", "comments"]

    def test_single_with_trailing_comma(self):
        assert parse_include("author,") == ["author"]


# ---------------------------------------------------------------------------
# parse_fields() tests
# ---------------------------------------------------------------------------

class TestParseFields:
    def test_single_type_single_field(self):
        result = parse_fields({"fields[posts]": "title"})
        assert result == {"posts": ["title"]}

    def test_single_type_multiple_fields(self):
        result = parse_fields({"fields[posts]": "title,body"})
        assert result == {"posts": ["title", "body"]}

    def test_multiple_types(self):
        result = parse_fields({
            "fields[posts]": "title,created_at",
            "fields[users]": "name",
        })
        assert result == {"posts": ["title", "created_at"], "users": ["name"]}

    def test_strips_whitespace_in_fields(self):
        result = parse_fields({"fields[posts]": "title, body , created_at"})
        assert result == {"posts": ["title", "body", "created_at"]}

    def test_ignores_non_fields_keys(self):
        result = parse_fields({"include": "author", "fields[posts]": "title"})
        assert result == {"posts": ["title"]}

    def test_empty_dict_returns_empty(self):
        assert parse_fields({}) == {}

    def test_no_fields_keys_returns_empty(self):
        assert parse_fields({"include": "author", "page": "1"}) == {}


# ---------------------------------------------------------------------------
# Sparse fieldset serialization tests
# ---------------------------------------------------------------------------

class TestSparseFieldsets:
    def test_single_resource_fields_filtered(self):
        post = PostResource(1, "Hello", "World", "2024-01-01")
        doc = post.serialize(fields={"posts": ["title"]})
        assert doc["data"]["attributes"] == {"title": "Hello"}

    def test_multiple_fields_filtered(self):
        post = PostResource(1, "Hello", "World", "2024-01-01")
        doc = post.serialize(fields={"posts": ["title", "body"]})
        assert doc["data"]["attributes"] == {"title": "Hello", "body": "World"}

    def test_fields_for_other_type_does_not_affect_this_resource(self):
        post = PostResource(1, "Hello", "World", "2024-01-01")
        doc = post.serialize(fields={"users": ["name"]})  # no "posts" key
        # all attributes should be present
        assert set(doc["data"]["attributes"].keys()) == {"title", "body", "created_at"}

    def test_included_resources_also_filtered(self):
        author = UserResource(5, "Alice", "alice@example.com", "admin")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize(
            include=["author"],
            fields={"users": ["name"]},
        )
        inc = next(i for i in doc["included"] if i["type"] == "users")
        assert inc["attributes"] == {"name": "Alice"}
        assert "email" not in inc["attributes"]

    def test_list_response_fields_filtered(self):
        posts = [
            PostResource(1, "A", "aa", "2024-01-01"),
            PostResource(2, "B", "bb", "2024-01-02"),
        ]
        doc = JsonAPIListResponse(posts).serialize(fields={"posts": ["title"]})
        for item in doc["data"]:
            assert list(item["attributes"].keys()) == ["title"]

    def test_combined_include_and_fields(self):
        """include= and fields[*]= should work together."""
        author = UserResource(10, "Bob", "bob@example.com", "editor")
        post = PostResource(1, "Post", "Body", author=author)
        doc = post.serialize(
            include=["author"],
            fields={"posts": ["title"], "users": ["name", "email"]},
        )
        assert doc["data"]["attributes"] == {"title": "Post"}
        inc = doc["included"][0]
        assert inc["attributes"] == {"name": "Bob", "email": "bob@example.com"}


# ---------------------------------------------------------------------------
# FastAPI ASGI __call__ integration tests
# ---------------------------------------------------------------------------

class TestFastAPIAsgiResponse:
    """Test that JsonAPIResponse instances can be returned directly from
    FastAPI endpoints (the ASGI __call__ path)."""

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        api = FastAPI()

        @api.get("/api/users/{id}")
        async def get_user(id: int):
            user = UserResource(id, "Alice", "alice@example.com", "admin")
            return user  # ← returned directly, no .serialize() call

        @api.get("/api/posts/{id}")
        async def get_post(id: int):
            author = UserResource(1, "Alice")
            post = PostResource(id, "My Post", "Body text", author=author)
            return post

        @api.get("/api/posts")
        async def list_posts():
            author = UserResource(1, "Alice")
            posts = [
                PostResource(1, "Post One", author=author),
                PostResource(2, "Post Two"),
            ]
            return JsonAPIListResponse(posts)

        return TestClient(api)

    def test_direct_return_gives_jsonapi_envelope(self, app):
        resp = app.get("/api/users/42")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "users"
        assert body["data"]["id"] == "42"
        assert body["data"]["attributes"]["name"] == "Alice"

    def test_content_type_is_vnd_api_json(self, app):
        resp = app.get("/api/users/1")
        assert "application/vnd.api+json" in resp.headers["content-type"]

    def test_include_query_param_parsed_automatically(self, app):
        resp = app.get("/api/posts/1?include=author")
        body = resp.json()
        assert "included" in body
        assert body["included"][0]["type"] == "users"

    def test_no_include_no_included_key(self, app):
        resp = app.get("/api/posts/1")
        body = resp.json()
        assert "included" not in body

    def test_fields_query_param_filtered(self, app):
        resp = app.get("/api/users/1?fields[users]=name")
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert list(attrs.keys()) == ["name"]

    def test_include_and_fields_together(self, app):
        resp = app.get("/api/posts/1?include=author&fields[users]=name")
        body = resp.json()
        assert "included" in body
        assert body["included"][0]["attributes"] == {"name": "Alice"}

    def test_list_response_direct_return(self, app):
        resp = app.get("/api/posts")
        body = resp.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 2

    def test_list_response_include_parsed(self, app):
        resp = app.get("/api/posts?include=author")
        body = resp.json()
        assert "included" in body
        assert body["included"][0]["type"] == "users"

    def test_list_response_fields_parsed(self, app):
        resp = app.get("/api/posts?fields[posts]=title")
        body = resp.json()
        for item in body["data"]:
            assert list(item["attributes"].keys()) == ["title"]

"""Tests for JsonResource serialization."""

from fastapi_startkit.jsonapi import JsonResource, _ResourceCollection


# ---------------------------------------------------------------------------
# Fake models
# ---------------------------------------------------------------------------


class FakeUser:
    def __init__(self, id_, name, email="user@example.com"):
        self.id = id_
        self.name = name
        self.email = email

    def serialize(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class FakePost:
    def __init__(self, id_, title, body, author=None):
        self.id = id_
        self.title = title
        self.body = body
        self.author = author

    def serialize(self):
        return {"id": self.id, "title": self.title, "body": self.body}


# ---------------------------------------------------------------------------
# Fixture resources
# ---------------------------------------------------------------------------


class UserResource(JsonResource[FakeUser]):
    pass  # type="users", auto-attrs


class PostResource(JsonResource[FakePost]):
    def to_relationships(self):
        if self.model.author is None:
            return None
        return {"author": UserResource(self.model.author)}


class PostWithLinksResource(PostResource):
    def to_links(self):
        return {"self": f"/api/posts/{self.id}"}

    def to_meta(self):
        return {"version": 1}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJsonAPIResponseStructure:
    def test_serialize_returns_dict(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert isinstance(doc, dict)

    def test_data_key_present(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert "data" in doc

    def test_data_type(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert doc["data"]["type"] == "posts"

    def test_data_id_as_string(self):
        post = PostResource(FakePost(42, "Hello", "World"))
        doc = post.serialize()
        assert doc["data"]["id"] == "42"

    def test_data_attributes(self):
        post = PostResource(FakePost(1, "My Title", "My Body"))
        doc = post.serialize()
        assert doc["data"]["attributes"] == {"title": "My Title", "body": "My Body"}

    def test_no_relationships_key_when_none(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert "relationships" not in doc["data"]

    def test_no_included_key_when_no_include(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize()
        assert "included" not in doc

    def test_no_links_key_when_none(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert "links" not in doc

    def test_no_meta_key_when_none(self):
        post = PostResource(FakePost(1, "Hello", "World"))
        doc = post.serialize()
        assert "meta" not in doc

    def test_links_present_when_overridden(self):
        post = PostWithLinksResource(FakePost(5, "Hello", "World"))
        doc = post.serialize()
        assert doc["links"] == {"self": "/api/posts/5"}

    def test_meta_present_when_overridden(self):
        post = PostWithLinksResource(FakePost(5, "Hello", "World"))
        doc = post.serialize()
        assert doc["meta"] == {"version": 1}


class TestJsonAPIResponseRelationships:
    def test_relationships_in_data_when_present(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize()
        assert "relationships" in doc["data"]
        assert "author" in doc["data"]["relationships"]

    def test_relationship_data_shape(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize()
        rel = doc["data"]["relationships"]["author"]["data"]
        assert rel == {"type": "users", "id": "10"}


class TestJsonAPIResponseInclude:
    def test_included_when_include_specified(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize(include=["author"])
        assert "included" in doc

    def test_included_contains_author(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize(include=["author"])
        included = doc["included"]
        assert len(included) == 1
        assert included[0]["type"] == "users"
        assert included[0]["id"] == "10"
        assert included[0]["attributes"]["name"] == "Alice"

    def test_no_included_when_rel_not_in_include(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize(include=["comments"])  # 'comments' does not exist
        assert "included" not in doc

    def test_no_included_key_when_include_is_empty_list(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize(include=[])
        assert "included" not in doc

    def test_no_duplicate_included_across_two_posts_same_author(self):
        """Duplicates should not appear even if processed by list response."""
        author = FakeUser(10, "Alice")
        post1 = PostResource(FakePost(1, "P1", "B1", author=author))
        post2 = PostResource(FakePost(2, "P2", "B2", author=author))
        doc = _ResourceCollection([post1, post2]).serialize(include=["author"])
        assert len(doc["included"]) == 1

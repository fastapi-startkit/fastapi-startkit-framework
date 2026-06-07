"""Tests for JsonAPIResponse serialization."""

from fastapi_startkit.jsonapi import JsonAPIResponse


# ---------------------------------------------------------------------------
# Fixture resources
# ---------------------------------------------------------------------------


class UserResource(JsonAPIResponse):
    type = "users"
    attributes = ["name", "email"]

    def __init__(self, id_, name, email="user@example.com"):
        self.id = id_
        self.name = name
        self.email = email

    def to_attributes(self):
        return {"name": self.name, "email": self.email}


class PostResource(JsonAPIResponse):
    type = "posts"
    attributes = ["title", "body"]

    def __init__(self, id_, title, body, author=None):
        self.id = id_
        self.title = title
        self.body = body
        self._author = author

    def to_attributes(self):
        return {"title": self.title, "body": self.body}

    def to_relationships(self):
        if self._author is None:
            return None
        return {"author": self._author}


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
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert isinstance(doc, dict)

    def test_data_key_present(self):
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert "data" in doc

    def test_data_type(self):
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert doc["data"]["type"] == "posts"

    def test_data_id_as_string(self):
        post = PostResource(42, "Hello", "World")
        doc = post.serialize()
        assert doc["data"]["id"] == "42"

    def test_data_attributes(self):
        post = PostResource(1, "My Title", "My Body")
        doc = post.serialize()
        assert doc["data"]["attributes"] == {"title": "My Title", "body": "My Body"}

    def test_no_relationships_key_when_none(self):
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert "relationships" not in doc["data"]

    def test_no_included_key_when_no_include(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize()
        assert "included" not in doc

    def test_no_links_key_when_none(self):
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert "links" not in doc

    def test_no_meta_key_when_none(self):
        post = PostResource(1, "Hello", "World")
        doc = post.serialize()
        assert "meta" not in doc

    def test_links_present_when_overridden(self):
        post = PostWithLinksResource(5, "Hello", "World")
        doc = post.serialize()
        assert doc["links"] == {"self": "/api/posts/5"}

    def test_meta_present_when_overridden(self):
        post = PostWithLinksResource(5, "Hello", "World")
        doc = post.serialize()
        assert doc["meta"] == {"version": 1}


class TestJsonAPIResponseRelationships:
    def test_relationships_in_data_when_present(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize()
        assert "relationships" in doc["data"]
        assert "author" in doc["data"]["relationships"]

    def test_relationship_data_shape(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize()
        rel = doc["data"]["relationships"]["author"]["data"]
        assert rel == {"type": "users", "id": "10"}


class TestJsonAPIResponseInclude:
    def test_included_when_include_specified(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize(include=["author"])
        assert "included" in doc

    def test_included_contains_author(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize(include=["author"])
        included = doc["included"]
        assert len(included) == 1
        assert included[0]["type"] == "users"
        assert included[0]["id"] == "10"
        assert included[0]["attributes"]["name"] == "Alice"

    def test_no_included_when_rel_not_in_include(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize(include=["comments"])  # 'comments' does not exist
        assert "included" not in doc

    def test_no_included_key_when_include_is_empty_list(self):
        author = UserResource(10, "Alice")
        post = PostResource(1, "Hello", "World", author=author)
        doc = post.serialize(include=[])
        assert "included" not in doc

    def test_no_duplicate_included_across_two_posts_same_author(self):
        """Duplicates should not appear even if processed by list response."""
        from fastapi_startkit.jsonapi import JsonAPIListResponse

        author = UserResource(10, "Alice")
        post1 = PostResource(1, "P1", "B1", author=author)
        post2 = PostResource(2, "P2", "B2", author=author)
        doc = JsonAPIListResponse([post1, post2]).serialize(include=["author"])
        assert len(doc["included"]) == 1


class TestJsonAPIResponseDefaultAttributes:
    """Test the default to_attributes() logic when attributes is a list."""

    def test_default_to_attributes_reads_instance_attrs(self):
        class TagResource(JsonAPIResponse):
            type = "tags"
            attributes = ["name", "slug"]

            def __init__(self, id_, name, slug):
                self.id = id_
                self.name = name
                self.slug = slug

        tag = TagResource(1, "Python", "python")
        doc = tag.serialize()
        assert doc["data"]["attributes"] == {"name": "Python", "slug": "python"}

    def test_default_to_attributes_returns_none_when_no_attrs(self):
        class EmptyResource(JsonAPIResponse):
            type = "empty"

            def __init__(self):
                self.id = 1

        resource = EmptyResource()
        doc = resource.serialize()
        assert "attributes" not in doc["data"]

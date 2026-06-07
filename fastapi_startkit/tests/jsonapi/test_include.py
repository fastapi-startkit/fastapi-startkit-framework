"""Tests for include= sideloading logic in JsonAPIResponse."""

from fastapi_startkit.jsonapi import JsonAPIResponse, JsonAPIListResponse


# ---------------------------------------------------------------------------
# Fixture resources — three-level hierarchy: Post → Author → Company
# ---------------------------------------------------------------------------


class CompanyResource(JsonAPIResponse):
    type = "companies"
    attributes = ["name"]

    def __init__(self, id_, name):
        self.id = id_
        self.name = name

    def to_attributes(self):
        return {"name": self.name}


class AuthorResource(JsonAPIResponse):
    type = "authors"
    attributes = ["username"]

    def __init__(self, id_, username, company=None):
        self.id = id_
        self.username = username
        self._company = company

    def to_attributes(self):
        return {"username": self.username}

    def to_relationships(self):
        if self._company is None:
            return None
        return {"company": self._company}


class CommentResource(JsonAPIResponse):
    type = "comments"
    attributes = ["body"]

    def __init__(self, id_, body):
        self.id = id_
        self.body = body

    def to_attributes(self):
        return {"body": self.body}


class PostResource(JsonAPIResponse):
    type = "posts"
    attributes = ["title"]

    def __init__(self, id_, title, author=None, comments=None):
        self.id = id_
        self.title = title
        self._author = author
        self._comments = comments or []

    def to_attributes(self):
        return {"title": self.title}

    def to_relationships(self):
        rels = {}
        if self._author is not None:
            rels["author"] = self._author
        for i, comment in enumerate(self._comments):
            rels[f"comment_{i}"] = comment
        return rels or None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIncludeSingleRelationship:
    def test_include_author_present(self):
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)
        doc = post.serialize(include=["author"])
        assert "included" in doc
        assert any(inc["type"] == "authors" and inc["id"] == "1" for inc in doc["included"])

    def test_include_uses_resource_attributes(self):
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)
        doc = post.serialize(include=["author"])
        inc = next(i for i in doc["included"] if i["type"] == "authors")
        assert inc["attributes"]["username"] == "alice"

    def test_include_non_existent_relationship_no_included(self):
        post = PostResource(10, "My Post")
        doc = post.serialize(include=["author"])
        assert "included" not in doc

    def test_include_none_equivalent_to_empty(self):
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)
        doc_none = post.serialize(include=None)
        doc_empty = post.serialize(include=[])
        assert "included" not in doc_none
        assert "included" not in doc_empty


class TestIncludeMultipleRelationships:
    def test_include_multiple_keys(self):
        author = AuthorResource(1, "alice")
        comment = CommentResource(100, "Great post!")
        post = PostResource(10, "My Post", author=author, comments=[comment])
        doc = post.serialize(include=["author", "comment_0"])
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" in types

    def test_include_only_requested_keys(self):
        author = AuthorResource(1, "alice")
        comment = CommentResource(100, "Great post!")
        post = PostResource(10, "My Post", author=author, comments=[comment])
        doc = post.serialize(include=["author"])
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" not in types


class TestIncludeDeduplication:
    def test_same_resource_not_duplicated(self):
        author = AuthorResource(1, "alice")
        # Two posts sharing the same author object.
        posts = [
            PostResource(1, "P1", author=author),
            PostResource(2, "P2", author=author),
        ]
        doc = JsonAPIListResponse(posts).serialize(include=["author"])
        author_entries = [i for i in doc["included"] if i["type"] == "authors"]
        assert len(author_entries) == 1


class TestIncludeRelationshipDataInDocument:
    def test_relationships_key_in_data_still_present(self):
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)
        doc = post.serialize(include=["author"])
        assert "relationships" in doc["data"]
        assert "author" in doc["data"]["relationships"]

    def test_relationship_linkage_is_correct(self):
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)
        doc = post.serialize(include=["author"])
        linkage = doc["data"]["relationships"]["author"]["data"]
        assert linkage == {"type": "authors", "id": "1"}


class TestIncludeFromQueryParam:
    """Simulate how FastAPI would pass the include= query parameter."""

    def test_include_from_comma_split(self):
        """Demonstrate parsing include= query string and passing to serialize()."""
        author = AuthorResource(1, "alice")
        post = PostResource(10, "My Post", author=author)

        # FastAPI endpoint would do: include_param.split(",")
        include_param = "author"
        include_list = [x.strip() for x in include_param.split(",")]

        doc = post.serialize(include=include_list)
        assert "included" in doc

    def test_include_multiple_from_comma_split(self):
        author = AuthorResource(1, "alice")
        comment = CommentResource(100, "Nice")
        post = PostResource(10, "My Post", author=author, comments=[comment])

        include_param = "author, comment_0"
        include_list = [x.strip() for x in include_param.split(",")]

        doc = post.serialize(include=include_list)
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" in types

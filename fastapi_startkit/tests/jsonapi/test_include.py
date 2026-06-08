"""Tests for include= sideloading logic in JsonResource."""

from fastapi_startkit.jsonapi import JsonResource, _ResourceCollection


# ---------------------------------------------------------------------------
# Fake models
# ---------------------------------------------------------------------------


class FakeCompany:
    def __init__(self, id_, name):
        self.id = id_
        self.name = name

    def serialize(self):
        return {"id": self.id, "name": self.name}


class FakeAuthor:
    def __init__(self, id_, username, company=None):
        self.id = id_
        self.username = username
        self.company = company

    def serialize(self):
        return {"id": self.id, "username": self.username}


class FakeComment:
    def __init__(self, id_, body):
        self.id = id_
        self.body = body

    def serialize(self):
        return {"id": self.id, "body": self.body}


class FakePost:
    def __init__(self, id_, title, author=None, comments=None):
        self.id = id_
        self.title = title
        self.author = author
        self.comments = comments or []

    def serialize(self):
        return {"id": self.id, "title": self.title}


# ---------------------------------------------------------------------------
# Fixture resources — three-level hierarchy: Post -> Author -> Company
# ---------------------------------------------------------------------------


class CompanyResource(JsonResource[FakeCompany]):
    pass  # type="companies", auto-attrs


class AuthorResource(JsonResource[FakeAuthor]):
    def to_relationships(self):
        if self.model.company is None:
            return None
        return {"company": CompanyResource(self.model.company)}


class CommentResource(JsonResource[FakeComment]):
    pass  # type="comments", auto-attrs


class PostResource(JsonResource[FakePost]):
    def to_relationships(self):
        rels = {}
        if self.model.author is not None:
            rels["author"] = AuthorResource(self.model.author)
        for i, comment in enumerate(self.model.comments):
            rels[f"comment_{i}"] = CommentResource(comment)
        return rels or None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIncludeSingleRelationship:
    def test_include_author_present(self):
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))
        doc = post.serialize(include=["author"])
        assert "included" in doc
        assert any(inc["type"] == "authors" and inc["id"] == "1" for inc in doc["included"])

    def test_include_uses_resource_attributes(self):
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))
        doc = post.serialize(include=["author"])
        inc = next(i for i in doc["included"] if i["type"] == "authors")
        assert inc["attributes"]["username"] == "alice"

    def test_include_non_existent_relationship_no_included(self):
        post = PostResource(FakePost(10, "My Post"))
        doc = post.serialize(include=["author"])
        assert "included" not in doc

    def test_include_none_equivalent_to_empty(self):
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))
        doc_none = post.serialize(include=None)
        doc_empty = post.serialize(include=[])
        assert "included" not in doc_none
        assert "included" not in doc_empty


class TestIncludeMultipleRelationships:
    def test_include_multiple_keys(self):
        author = FakeAuthor(1, "alice")
        comment = FakeComment(100, "Great post!")
        post = PostResource(FakePost(10, "My Post", author=author, comments=[comment]))
        doc = post.serialize(include=["author", "comment_0"])
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" in types

    def test_include_only_requested_keys(self):
        author = FakeAuthor(1, "alice")
        comment = FakeComment(100, "Great post!")
        post = PostResource(FakePost(10, "My Post", author=author, comments=[comment]))
        doc = post.serialize(include=["author"])
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" not in types


class TestIncludeDeduplication:
    def test_same_resource_not_duplicated(self):
        author = FakeAuthor(1, "alice")
        # Two posts sharing the same author object.
        posts = [
            PostResource(FakePost(1, "P1", author=author)),
            PostResource(FakePost(2, "P2", author=author)),
        ]
        doc = _ResourceCollection(posts).serialize(include=["author"])
        author_entries = [i for i in doc["included"] if i["type"] == "authors"]
        assert len(author_entries) == 1


class TestIncludeRelationshipDataInDocument:
    def test_relationships_key_in_data_still_present(self):
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))
        doc = post.serialize(include=["author"])
        assert "relationships" in doc["data"]
        assert "author" in doc["data"]["relationships"]

    def test_relationship_linkage_is_correct(self):
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))
        doc = post.serialize(include=["author"])
        linkage = doc["data"]["relationships"]["author"]["data"]
        assert linkage == {"type": "authors", "id": "1"}


class TestIncludeFromQueryParam:
    """Simulate how FastAPI would pass the include= query parameter."""

    def test_include_from_comma_split(self):
        """Demonstrate parsing include= query string and passing to serialize()."""
        author = FakeAuthor(1, "alice")
        post = PostResource(FakePost(10, "My Post", author=author))

        # FastAPI endpoint would do: include_param.split(",")
        include_param = "author"
        include_list = [x.strip() for x in include_param.split(",")]

        doc = post.serialize(include=include_list)
        assert "included" in doc

    def test_include_multiple_from_comma_split(self):
        author = FakeAuthor(1, "alice")
        comment = FakeComment(100, "Nice")
        post = PostResource(FakePost(10, "My Post", author=author, comments=[comment]))

        include_param = "author, comment_0"
        include_list = [x.strip() for x in include_param.split(",")]

        doc = post.serialize(include=include_list)
        types = {inc["type"] for inc in doc["included"]}
        assert "authors" in types
        assert "comments" in types

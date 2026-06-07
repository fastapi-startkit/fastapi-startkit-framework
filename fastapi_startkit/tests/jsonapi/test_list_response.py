"""Tests for JsonAPIListResponse serialization."""

from fastapi_startkit.jsonapi import JsonAPIListResponse, JsonAPIResponse


# ---------------------------------------------------------------------------
# Fixture resources
# ---------------------------------------------------------------------------


class AuthorResource(JsonAPIResponse):
    type = "authors"
    attributes = ["name"]

    def __init__(self, id_, name):
        self.id = id_
        self.name = name

    def to_attributes(self):
        return {"name": self.name}


class ArticleResource(JsonAPIResponse):
    type = "articles"
    attributes = ["title"]

    def __init__(self, id_, title, author=None):
        self.id = id_
        self.title = title
        self._author = author

    def to_attributes(self):
        return {"title": self.title}

    def to_relationships(self):
        if self._author is None:
            return None
        return {"author": self._author}


class ArticleListWithMeta(JsonAPIListResponse):
    def to_meta(self):
        return {"total": len(self._items)}

    def to_links(self):
        return {"self": "/api/articles"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJsonAPIListResponseStructure:
    def test_data_is_list(self):
        items = [ArticleResource(1, "A"), ArticleResource(2, "B")]
        doc = JsonAPIListResponse(items).serialize()
        assert isinstance(doc["data"], list)

    def test_data_length(self):
        items = [ArticleResource(i, f"Article {i}") for i in range(3)]
        doc = JsonAPIListResponse(items).serialize()
        assert len(doc["data"]) == 3

    def test_each_item_has_type_and_id(self):
        items = [ArticleResource(1, "A"), ArticleResource(2, "B")]
        doc = JsonAPIListResponse(items).serialize()
        for item_data in doc["data"]:
            assert "type" in item_data
            assert "id" in item_data

    def test_data_types(self):
        items = [ArticleResource(1, "A")]
        doc = JsonAPIListResponse(items).serialize()
        assert doc["data"][0]["type"] == "articles"

    def test_empty_list(self):
        doc = JsonAPIListResponse([]).serialize()
        assert doc["data"] == []
        assert "included" not in doc

    def test_no_links_by_default(self):
        doc = JsonAPIListResponse([ArticleResource(1, "A")]).serialize()
        assert "links" not in doc

    def test_no_meta_by_default(self):
        doc = JsonAPIListResponse([ArticleResource(1, "A")]).serialize()
        assert "meta" not in doc

    def test_links_when_overridden(self):
        items = [ArticleResource(1, "A")]
        doc = ArticleListWithMeta(items).serialize()
        assert doc["links"] == {"self": "/api/articles"}

    def test_meta_when_overridden(self):
        items = [ArticleResource(1, "A"), ArticleResource(2, "B")]
        doc = ArticleListWithMeta(items).serialize()
        assert doc["meta"] == {"total": 2}


class TestJsonAPIListResponseInclude:
    def test_included_when_include_specified(self):
        author = AuthorResource(5, "Bob")
        items = [ArticleResource(1, "A", author=author)]
        doc = JsonAPIListResponse(items).serialize(include=["author"])
        assert "included" in doc
        assert len(doc["included"]) == 1

    def test_included_contains_correct_resource(self):
        author = AuthorResource(5, "Bob")
        items = [ArticleResource(1, "A", author=author)]
        doc = JsonAPIListResponse(items).serialize(include=["author"])
        inc = doc["included"][0]
        assert inc["type"] == "authors"
        assert inc["id"] == "5"
        assert inc["attributes"]["name"] == "Bob"

    def test_deduplication_across_items(self):
        """Same author linked from two articles must appear only once."""
        author = AuthorResource(5, "Bob")
        items = [
            ArticleResource(1, "A", author=author),
            ArticleResource(2, "B", author=author),
        ]
        doc = JsonAPIListResponse(items).serialize(include=["author"])
        assert len(doc["included"]) == 1

    def test_multiple_distinct_authors_included(self):
        alice = AuthorResource(1, "Alice")
        bob = AuthorResource(2, "Bob")
        items = [
            ArticleResource(1, "A", author=alice),
            ArticleResource(2, "B", author=bob),
        ]
        doc = JsonAPIListResponse(items).serialize(include=["author"])
        assert len(doc["included"]) == 2
        ids = {inc["id"] for inc in doc["included"]}
        assert ids == {"1", "2"}

    def test_no_included_when_not_in_include(self):
        author = AuthorResource(5, "Bob")
        items = [ArticleResource(1, "A", author=author)]
        doc = JsonAPIListResponse(items).serialize(include=["comments"])
        assert "included" not in doc

    def test_no_included_on_empty_include(self):
        author = AuthorResource(5, "Bob")
        items = [ArticleResource(1, "A", author=author)]
        doc = JsonAPIListResponse(items).serialize(include=[])
        assert "included" not in doc

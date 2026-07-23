"""Tests for ResourceCollection serialization."""

from fastapi_startkit.jsonapi import JsonResource, ResourceCollection


# ---------------------------------------------------------------------------
# Fake models
# ---------------------------------------------------------------------------


class FakeAuthor:
    def __init__(self, id_, name):
        self.id = id_
        self.name = name

    def serialize(self):
        return {"id": self.id, "name": self.name}


class FakeArticle:
    def __init__(self, id_, title, author=None):
        self.id = id_
        self.title = title
        self.author = author

    def serialize(self):
        return {"id": self.id, "title": self.title}


# ---------------------------------------------------------------------------
# Fixture resources
# ---------------------------------------------------------------------------


class AuthorResource(JsonResource[FakeAuthor]):
    pass  # type="authors", auto-attrs


class ArticleResource(JsonResource[FakeArticle]):
    def to_relationships(self):
        if self.model.author is None:
            return None
        return {"author": AuthorResource(self.model.author)}


class ArticleListWithMeta(ResourceCollection):
    def to_meta(self):
        return {"total": len(self._items)}

    def to_links(self):
        return {"self": "/api/articles"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJsonAPIListResponseStructure:
    def test_data_is_list(self):
        items = [ArticleResource(FakeArticle(1, "A")), ArticleResource(FakeArticle(2, "B"))]
        doc = ResourceCollection(items).serialize()
        assert isinstance(doc["data"], list)

    def test_data_length(self):
        items = [ArticleResource(FakeArticle(i, f"Article {i}")) for i in range(3)]
        doc = ResourceCollection(items).serialize()
        assert len(doc["data"]) == 3

    def test_each_item_has_type_and_id(self):
        items = [ArticleResource(FakeArticle(1, "A")), ArticleResource(FakeArticle(2, "B"))]
        doc = ResourceCollection(items).serialize()
        for item_data in doc["data"]:
            assert "type" in item_data
            assert "id" in item_data

    def test_data_types(self):
        items = [ArticleResource(FakeArticle(1, "A"))]
        doc = ResourceCollection(items).serialize()
        assert doc["data"][0]["type"] == "articles"

    def test_empty_list(self):
        doc = ResourceCollection([]).serialize()
        assert doc["data"] == []
        assert "included" not in doc

    def test_no_links_by_default(self):
        doc = ResourceCollection([ArticleResource(FakeArticle(1, "A"))]).serialize()
        assert "links" not in doc

    def test_no_meta_by_default(self):
        doc = ResourceCollection([ArticleResource(FakeArticle(1, "A"))]).serialize()
        assert "meta" not in doc

    def test_links_when_overridden(self):
        items = [ArticleResource(FakeArticle(1, "A"))]
        doc = ArticleListWithMeta(items).serialize()
        assert doc["links"] == {"self": "/api/articles"}

    def test_meta_when_overridden(self):
        items = [ArticleResource(FakeArticle(1, "A")), ArticleResource(FakeArticle(2, "B"))]
        doc = ArticleListWithMeta(items).serialize()
        assert doc["meta"] == {"total": 2}


class TestJsonAPIListResponseInclude:
    def test_included_when_include_specified(self):
        author = FakeAuthor(5, "Bob")
        items = [ArticleResource(FakeArticle(1, "A", author=author))]
        doc = ResourceCollection(items).include("author").serialize()
        assert "included" in doc
        assert len(doc["included"]) == 1

    def test_included_contains_correct_resource(self):
        author = FakeAuthor(5, "Bob")
        items = [ArticleResource(FakeArticle(1, "A", author=author))]
        doc = ResourceCollection(items).include("author").serialize()
        inc = doc["included"][0]
        assert inc["type"] == "authors"
        assert inc["id"] == "5"
        assert inc["attributes"]["name"] == "Bob"

    def test_deduplication_across_items(self):
        """Same author linked from two articles must appear only once."""
        author = FakeAuthor(5, "Bob")
        items = [
            ArticleResource(FakeArticle(1, "A", author=author)),
            ArticleResource(FakeArticle(2, "B", author=author)),
        ]
        doc = ResourceCollection(items).include("author").serialize()
        assert len(doc["included"]) == 1

    def test_multiple_distinct_authors_included(self):
        alice = FakeAuthor(1, "Alice")
        bob = FakeAuthor(2, "Bob")
        items = [
            ArticleResource(FakeArticle(1, "A", author=alice)),
            ArticleResource(FakeArticle(2, "B", author=bob)),
        ]
        doc = ResourceCollection(items).include("author").serialize()
        assert len(doc["included"]) == 2
        ids = {inc["id"] for inc in doc["included"]}
        assert ids == {"1", "2"}

    def test_no_included_when_not_in_include(self):
        author = FakeAuthor(5, "Bob")
        items = [ArticleResource(FakeArticle(1, "A", author=author))]
        doc = ResourceCollection(items).include("comments").serialize()
        assert "included" not in doc

    def test_no_included_on_empty_include(self):
        author = FakeAuthor(5, "Bob")
        items = [ArticleResource(FakeArticle(1, "A", author=author))]
        doc = ResourceCollection(items).serialize()
        assert "included" not in doc

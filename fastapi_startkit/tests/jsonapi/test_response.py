"""Tests for JsonResource serialization."""

from fastapi_startkit.jsonapi import JsonResource, ResourceCollection


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
    # Class reference — framework auto-wraps self.model.author with UserResource
    def to_relationships(self):
        return {"author": UserResource}


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
        attrs = doc["data"]["attributes"]
        assert attrs["title"] == "My Title"
        assert attrs["body"] == "My Body"

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
        doc = post.include("author").serialize()
        assert "included" in doc

    def test_included_contains_author(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.include("author").serialize()
        included = doc["included"]
        assert len(included) == 1
        assert included[0]["type"] == "users"
        assert included[0]["id"] == "10"
        assert included[0]["attributes"]["name"] == "Alice"

    def test_no_included_when_rel_not_in_include(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.include("comments").serialize()  # 'comments' does not exist
        assert "included" not in doc

    def test_no_included_key_when_include_is_empty_list(self):
        author = FakeUser(10, "Alice")
        post = PostResource(FakePost(1, "Hello", "World", author=author))
        doc = post.serialize()
        assert "included" not in doc

    def test_no_duplicate_included_across_two_posts_same_author(self):
        """Duplicates should not appear even if processed by list response."""
        author = FakeUser(10, "Alice")
        post1 = PostResource(FakePost(1, "P1", "B1", author=author))
        post2 = PostResource(FakePost(2, "P2", "B2", author=author))
        doc = ResourceCollection([post1, post2]).include("author").serialize()
        assert len(doc["included"]) == 1


class TestRelationshipForms:
    """to_relationships() accepts three equivalent value forms."""

    def test_class_reference_auto_wraps_model_attribute(self):
        """``UserResource`` → framework reads model.author and wraps it."""

        class AuthorResource(JsonResource[FakeUser]):
            pass

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                return {"author": AuthorResource}

        author = FakeUser(5, "Bob")
        post = FakePost(1, "Hi", "There", author=author)
        doc = ArticleResource(post).serialize()
        assert "author" in doc["data"]["relationships"]
        assert doc["data"]["relationships"]["author"]["data"]["id"] == "5"

    def test_class_reference_none_when_attribute_missing(self):
        """Class reference skips the key when model attribute is None/absent."""

        class AuthorResource(JsonResource[FakeUser]):
            pass

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                return {"author": AuthorResource}

        post = FakePost(1, "Hi", "There", author=None)
        doc = ArticleResource(post).serialize()
        assert "relationships" not in doc["data"]

    def test_lambda_callable(self):
        """Lambda is called with no args; its return value is used directly."""

        class AuthorResource(JsonResource[FakeUser]):
            pass

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                return {
                    "author": lambda: AuthorResource(self.model.author),
                }

        author = FakeUser(7, "Carol")
        post = FakePost(1, "Hi", "There", author=author)
        doc = ArticleResource(post).serialize()
        assert doc["data"]["relationships"]["author"]["data"]["id"] == "7"

    def test_explicit_instance(self):
        """Passing an already-constructed JsonResource instance works too."""

        class AuthorResource(JsonResource[FakeUser]):
            pass

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                return {"author": AuthorResource(self.model.author)}

        author = FakeUser(9, "Dave")
        post = FakePost(1, "Hi", "There", author=author)
        doc = ArticleResource(post).serialize()
        assert doc["data"]["relationships"]["author"]["data"]["id"] == "9"

    def test_collection_relationship_produces_array_linkage(self):
        """A ResourceCollection value produces ``{"data": [...]}`` linkage."""

        class CommentResource(JsonResource[FakeUser]):
            type = "comments"

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                comments = [
                    CommentResource(FakeUser(1, "c1")),
                    CommentResource(FakeUser(2, "c2")),
                ]
                return {"comments": ResourceCollection(comments)}

        post = FakePost(1, "Hi", "There")
        doc = ArticleResource(post).serialize()
        linkage = doc["data"]["relationships"]["comments"]["data"]
        assert isinstance(linkage, list)
        assert len(linkage) == 2
        assert linkage[0] == {"type": "comments", "id": "1"}

    def test_collection_relationship_included_when_sideloaded(self):
        """include("comments") sideloads all items from a collection relationship."""

        class CommentResource(JsonResource[FakeUser]):
            type = "comments"

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                comments = [
                    CommentResource(FakeUser(1, "c1")),
                    CommentResource(FakeUser(2, "c2")),
                ]
                return {"comments": ResourceCollection(comments)}

        post = FakePost(1, "Hi", "There")
        doc = ArticleResource(post).include("comments").serialize()
        assert len(doc["included"]) == 2
        assert all(i["type"] == "comments" for i in doc["included"])

    # ------------------------------------------------------------------
    # Auto-wrapping: no ResourceCollection() initialisation needed
    # ------------------------------------------------------------------

    def test_plain_list_auto_wrapped(self):
        """Returning a plain list auto-wraps it in ResourceCollection."""

        class CommentResource(JsonResource[FakeUser]):
            type = "comments"

        class ArticleResource(JsonResource[FakePost]):
            def to_relationships(self):
                # No ResourceCollection(...) needed
                return {
                    "comments": [
                        CommentResource(FakeUser(1, "c1")),
                        CommentResource(FakeUser(2, "c2")),
                    ]
                }

        post = FakePost(1, "Hi", "There")
        doc = ArticleResource(post).include("comments").serialize()
        assert len(doc["included"]) == 2

    def test_lambda_using_collection(self):
        """Lambda calls CommentResource.collection() for custom/filtered data."""

        class FakePostWithComments:
            def __init__(self, id_, comments):
                self.id = id_
                self.comments = comments

            def serialize(self):
                return {"id": self.id}

        class CommentResource(JsonResource[FakeUser]):
            type = "comments"

        class ArticleResource(JsonResource[FakePostWithComments]):
            def to_relationships(self):
                return {"comments": lambda: CommentResource.collection(self.model.comments)}

        comments = [FakeUser(1, "c1"), FakeUser(2, "c2")]
        post = FakePostWithComments(1, comments)
        doc = ArticleResource(post).include("comments").serialize()
        assert len(doc["included"]) == 2

    def test_class_reference_with_list_attribute_auto_collects(self):
        """Class reference on a list attribute calls .collection() automatically."""

        class FakePostWithComments:
            def __init__(self, id_):
                self.id = id_
                self.comments = [FakeUser(1, "c1"), FakeUser(2, "c2")]

            def serialize(self):
                return {"id": self.id}

        class CommentResource(JsonResource[FakeUser]):
            type = "comments"

        class ArticleResource(JsonResource[FakePostWithComments]):
            def to_relationships(self):
                return {"comments": CommentResource}

        post = FakePostWithComments(1)
        doc = ArticleResource(post).include("comments").serialize()
        assert len(doc["included"]) == 2
        assert all(i["type"] == "comments" for i in doc["included"])

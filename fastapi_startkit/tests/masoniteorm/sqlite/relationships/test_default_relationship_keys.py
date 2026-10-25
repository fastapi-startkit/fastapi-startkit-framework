import warnings

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, HasOne, Model
from fastapi_startkit.masoniteorm.relationships import HasOneThrough

from ..test_case import TestCase

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)

    class DefaultKeyWriter(Model):
        __table__ = "writers"
        __timestamps__ = False

        biography = HasOne["DefaultKeyBiography"]()
        posts = HasMany["DefaultKeyPost"]()
        latest_media = HasOneThrough(["DefaultKeyMedia", "DefaultKeyPost"])

    class DefaultKeyBiography(Model):
        __table__ = "biographies"
        __timestamps__ = False

        writer = BelongsTo["DefaultKeyWriter"]()

    class DefaultKeyPost(Model):
        __table__ = "posts"
        __timestamps__ = False

        writer = BelongsTo["DefaultKeyWriter"]()
        media = HasMany("DefaultKeyMedia")
        tags = BelongsToMany["DefaultKeyTag"]()

    class DefaultKeyMedia(Model):
        __table__ = "media"
        __timestamps__ = False

        post = BelongsTo("DefaultKeyPost")

    class DefaultKeyTag(Model):
        __table__ = "tags"
        __timestamps__ = False

        posts = BelongsToMany["DefaultKeyPost"]()


class TestDefaultRelationshipKeys(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        schema = self.schema.on("default")

        async with await schema.create_table_if_not_exists("writers") as table:
            table.id()
            table.string("name")

        async with await schema.create_table_if_not_exists("biographies") as table:
            table.id()
            table.integer("writer_id")
            table.string("body")

        async with await schema.create_table_if_not_exists("posts") as table:
            table.id()
            table.integer("writer_id")
            table.string("title")

        async with await schema.create_table_if_not_exists("media") as table:
            table.id()
            table.integer("post_id")
            table.string("path")

        async with await schema.create_table_if_not_exists("tags") as table:
            table.id()
            table.string("name")

        async with await schema.create_table_if_not_exists("post_tag") as table:
            table.id()
            table.integer("post_id")
            table.integer("tag_id")

        ada = await DefaultKeyWriter.create({"name": "Ada"})
        await DefaultKeyWriter.create({"name": "Grace"})
        await DefaultKeyBiography.create({"writer_id": ada.id, "body": "Analyst"})
        post = await DefaultKeyPost.create({"writer_id": ada.id, "title": "Engines"})
        await DefaultKeyPost.create({"writer_id": ada.id, "title": "Notes"})
        await DefaultKeyMedia.create({"post_id": post.id, "path": "engine.png"})
        tag = await DefaultKeyTag.create({"name": "math"})
        await DefaultKeyTag.create({"name": "unused"})
        await DefaultKeyPost.tags.attach(post, tag)

    def test_keys_are_inferred_on_class_access(self):
        assert (DefaultKeyWriter.posts.local_key, DefaultKeyWriter.posts.foreign_key) == ("id", "writer_id")
        assert (DefaultKeyWriter.biography.local_key, DefaultKeyWriter.biography.foreign_key) == ("id", "writer_id")
        assert (DefaultKeyPost.writer.local_key, DefaultKeyPost.writer.foreign_key) == ("writer_id", "id")
        assert (DefaultKeyMedia.post.local_key, DefaultKeyMedia.post.foreign_key) == ("post_id", "id")

        tags = DefaultKeyPost.tags
        assert (tags._table, tags.local_key, tags.foreign_key) == ("post_tag", "post_id", "tag_id")
        assert (tags.local_owner_key, tags.other_owner_key) == ("id", "id")

        posts = DefaultKeyTag.posts
        assert (posts._table, posts.local_key, posts.foreign_key) == ("post_tag", "tag_id", "post_id")

        through = DefaultKeyWriter.latest_media
        assert (through.local_key, through.local_owner_key) == ("id", "writer_id")
        assert (through.foreign_key, through.other_owner_key) == ("id", "post_id")

    async def test_eager_loads_default_key_relationships(self):
        posts = await DefaultKeyPost.with_("writer", "tags", "media").where("title", "Engines").get()
        post = posts.first()

        assert post.writer.name == "Ada"
        assert [tag.name for tag in post.tags] == ["math"]
        assert [media.path for media in post.media] == ["engine.png"]

        media = await DefaultKeyMedia.with_("post").first_or_fail()
        assert media.post.title == "Engines"

        tag = await DefaultKeyTag.with_("posts").where("name", "math").first_or_fail()
        assert [item.title for item in tag.posts] == ["Engines"]

    async def test_eager_loads_default_key_has_one_and_has_many(self):
        writer = await DefaultKeyWriter.with_("biography", "posts").where("name", "Ada").first_or_fail()

        assert writer.biography.body == "Analyst"
        assert sorted(post.title for post in writer.posts) == ["Engines", "Notes"]

        biography = await DefaultKeyBiography.with_("writer").first_or_fail()
        assert biography.writer.name == "Ada"

    async def test_eager_loads_default_key_has_one_through(self):
        writer = await DefaultKeyWriter.with_("latest_media").where("name", "Ada").first_or_fail()

        assert writer.latest_media.path == "engine.png"
        assert writer.latest_media.id is not None

        lonely = await DefaultKeyWriter.with_("latest_media").where("name", "Grace").first_or_fail()
        assert lonely.latest_media is None

    async def test_existence_queries_correlate_default_keys(self):
        with_posts = await DefaultKeyWriter.where_has("posts").get()
        assert [writer.name for writer in with_posts] == ["Ada"]

        engines = await DefaultKeyWriter.where_has("posts", lambda query: query.where("title", "Engines")).get()
        assert [writer.name for writer in engines] == ["Ada"]

        tagged = await DefaultKeyTag.where_has("posts").get()
        assert [tag.name for tag in tagged] == ["math"]

        with_biography = await DefaultKeyWriter.where_has("biography").get()
        assert [writer.name for writer in with_biography] == ["Ada"]

        with_writer = await DefaultKeyPost.where_has("writer", lambda query: query.where("name", "Ada")).get()
        assert sorted(post.title for post in with_writer) == ["Engines", "Notes"]

        tagged_posts = await DefaultKeyPost.where_has("tags").get()
        assert [post.title for post in tagged_posts] == ["Engines"]

        with_media = await DefaultKeyWriter.where_has("latest_media").get()
        assert [writer.name for writer in with_media] == ["Ada"]

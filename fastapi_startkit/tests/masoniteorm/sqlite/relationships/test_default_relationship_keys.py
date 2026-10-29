import gc
import warnings
import weakref

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, HasOne, Model
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.relationships import BaseRelationship, HasOneThrough
from fastapi_startkit.masoniteorm.relationships.BaseRelationship import RelationshipKey

from ..test_case import TestCase

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)

    class Novelist(Model):
        __timestamps__ = False

        memoir = HasOne["Memoir"]()
        essays = HasMany["Essay"]()
        latest_media = HasOneThrough(["Media", "Essay"])

    class Memoir(Model):
        __timestamps__ = False

        novelist = BelongsTo["Novelist"]()

    class Essay(Model):
        __timestamps__ = False

        novelist = BelongsTo["Novelist"]()
        media = HasMany("Media")
        labels = BelongsToMany["Label"]()

    class Media(Model):
        __table__ = "media"
        __timestamps__ = False

        essay = BelongsTo("Essay")
        labels = BelongsToMany["Label"]()

    class Label(Model):
        __table__ = "blog_labels"
        __timestamps__ = False

        essays = BelongsToMany["Essay"]()

    class KeyAccount(Model):
        __primary_key__ = "uuid"

        setting = HasOne["KeyAccountNote"]()
        notes = HasMany["KeyAccountNote"]()

    class KeyAccountNote(Model):
        account = BelongsTo["KeyAccount"]()

    class KeyBaseItem(Model):
        notes = HasMany["KeyAccountNote"]()
        explicit_notes = HasMany["KeyAccountNote"](foreign_key="owner_id")

    class KeyInvoice(KeyBaseItem):
        pass

    class PlainRelationship(BaseRelationship):
        pass

    class KeyPlainOwner(Model):
        plain = PlainRelationship("KeyAccountNote")


def keys(relationship):
    return relationship.local_key, relationship.foreign_key


def test_keys_follow_the_owner_class_name():
    assert keys(Novelist.essays) == ("id", "novelist_id")
    assert keys(Novelist.memoir) == ("id", "novelist_id")
    assert keys(Essay.novelist) == ("novelist_id", "id")
    assert keys(Media.essay) == ("essay_id", "id")


def test_pivot_table_and_keys_follow_sorted_class_names():
    labels = Essay.labels
    assert (labels._table, *keys(labels)) == ("essay_label", "essay_id", "label_id")
    assert (labels.local_owner_key, labels.other_owner_key) == ("id", "id")

    assert (Label.essays._table, *keys(Label.essays)) == ("essay_label", "label_id", "essay_id")


def test_irregular_plural_class_names_are_not_singularized():
    assert (Media.labels._table, *keys(Media.labels)) == ("label_media", "media_id", "label_id")


def test_relationship_key_is_a_descriptor_at_class_level():
    assert isinstance(BaseRelationship.local_key, RelationshipKey)
    assert isinstance(BelongsToMany._table, RelationshipKey)


def test_relationships_without_inferred_keys_leave_them_unset():
    assert keys(KeyPlainOwner.plain) == (None, None)


def test_custom_table_does_not_change_key_names():
    assert keys(Label.essays)[0] == "label_id"
    assert Label.essays._table == "essay_label"


def test_has_one_through_keys_follow_class_names():
    through = Novelist.latest_media
    assert (through.local_key, through.local_owner_key) == ("id", "novelist_id")
    assert (through.foreign_key, through.other_owner_key) == ("id", "essay_id")


def test_custom_primary_key_is_used_for_default_keys():
    assert keys(KeyAccount.setting) == ("uuid", "key_account_uuid")
    assert keys(KeyAccount.notes) == ("uuid", "key_account_uuid")
    assert keys(KeyAccountNote.account) == ("account_uuid", "uuid")


def test_inherited_relationships_bind_to_the_accessing_class():
    assert keys(KeyBaseItem.notes) == ("id", "key_base_item_id")
    assert keys(KeyInvoice.notes) == ("id", "key_invoice_id")
    assert KeyInvoice.notes.owner_class is KeyInvoice
    assert KeyInvoice.notes is KeyInvoice.notes
    assert keys(KeyInvoice.explicit_notes) == ("id", "owner_id")


def test_bound_relationships_do_not_keep_subclasses_alive():
    def declare():
        class KeyTransientItem(KeyBaseItem):
            pass

        assert keys(KeyTransientItem.notes) == ("id", "key_transient_item_id")
        Registry._models.pop("KeyTransientItem")
        Registry._morph_map.pop("KeyTransientItem")
        Registry._reverse_map.pop(KeyTransientItem)
        return weakref.ref(KeyTransientItem)

    subclass = declare()
    gc.collect()

    assert subclass() is None
    assert keys(KeyBaseItem.notes) == ("id", "key_base_item_id")


class TestDefaultRelationshipKeys(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        schema = self.schema.on("default")

        async with await schema.create_table_if_not_exists("novelists") as table:
            table.id()
            table.string("name")

        async with await schema.create_table_if_not_exists("memoirs") as table:
            table.id()
            table.integer("novelist_id")
            table.string("body")

        async with await schema.create_table_if_not_exists("essays") as table:
            table.id()
            table.integer("novelist_id")
            table.string("title")

        async with await schema.create_table_if_not_exists("media") as table:
            table.id()
            table.integer("essay_id")
            table.string("path")

        async with await schema.create_table_if_not_exists("blog_labels") as table:
            table.id()
            table.string("name")

        async with await schema.create_table_if_not_exists("essay_label") as table:
            table.id()
            table.integer("essay_id")
            table.integer("label_id")

        ada = await Novelist.create({"name": "Ada"})
        await Novelist.create({"name": "Grace"})
        await Memoir.create({"novelist_id": ada.id, "body": "Analyst"})
        essay = await Essay.create({"novelist_id": ada.id, "title": "Engines"})
        await Essay.create({"novelist_id": ada.id, "title": "Notes"})
        await Media.create({"essay_id": essay.id, "path": "engine.png"})
        label = await Label.create({"name": "math"})
        await Label.create({"name": "unused"})
        await Essay.labels.attach(essay, label)

    async def test_eager_loads_default_key_relationships(self):
        essays = await Essay.with_("novelist", "labels", "media").where("title", "Engines").get()
        essay = essays.first()

        assert essay.novelist.name == "Ada"
        assert [label.name for label in essay.labels] == ["math"]
        assert [media.path for media in essay.media] == ["engine.png"]

        media = await Media.with_("essay").first_or_fail()
        assert media.essay.title == "Engines"

        label = await Label.with_("essays").where("name", "math").first_or_fail()
        assert [item.title for item in label.essays] == ["Engines"]

    async def test_eager_loads_default_key_has_one_and_has_many(self):
        novelist = await Novelist.with_("memoir", "essays").where("name", "Ada").first_or_fail()

        assert novelist.memoir.body == "Analyst"
        assert sorted(essay.title for essay in novelist.essays) == ["Engines", "Notes"]

        memoir = await Memoir.with_("novelist").first_or_fail()
        assert memoir.novelist.name == "Ada"

    async def test_eager_loads_default_key_has_one_through(self):
        novelist = await Novelist.with_("latest_media").where("name", "Ada").first_or_fail()

        assert novelist.latest_media.path == "engine.png"
        assert novelist.latest_media.id is not None

        lonely = await Novelist.with_("latest_media").where("name", "Grace").first_or_fail()
        assert lonely.latest_media is None

    async def test_existence_queries_correlate_default_keys(self):
        with_essays = await Novelist.where_has("essays").get()
        assert [novelist.name for novelist in with_essays] == ["Ada"]

        engines = await Novelist.where_has("essays", lambda query: query.where("title", "Engines")).get()
        assert [novelist.name for novelist in engines] == ["Ada"]

        labelled = await Label.where_has("essays").get()
        assert [label.name for label in labelled] == ["math"]

        with_memoir = await Novelist.where_has("memoir").get()
        assert [novelist.name for novelist in with_memoir] == ["Ada"]

        by_ada = await Essay.where_has("novelist", lambda query: query.where("name", "Ada")).get()
        assert sorted(essay.title for essay in by_ada) == ["Engines", "Notes"]

        labelled_essays = await Essay.where_has("labels").get()
        assert [essay.title for essay in labelled_essays] == ["Engines"]

        with_media = await Novelist.where_has("latest_media").get()
        assert [novelist.name for novelist in with_media] == ["Ada"]

    async def test_belongs_to_many_existence_query_with_callback(self):
        label_ids = [label.id for label in await Label.where("name", "math").get()]
        unused_ids = [label.id for label in await Label.where("name", "unused").get()]

        math = await Essay.where_has("labels", lambda query: label_ids).get()
        assert [essay.title for essay in math] == ["Engines"]

        unused = await Essay.where_has("labels", lambda query: unused_ids).get()
        assert unused.count() == 0

        either = (
            await Essay.where_has("labels", lambda query: unused_ids)
            .or_where_has("labels", lambda query: label_ids)
            .get()
        )
        assert [essay.title for essay in either] == ["Engines"]

from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.collection import Collection
from fastapi_startkit.masoniteorm.models.registry import Registry
from fastapi_startkit.masoniteorm.relationships import MorphMany, MorphOne, MorphTo
from ..test_case import TestCase


def first_medium(self):
    return LexemeMedia


class LexemeMedia(Model):
    __table__ = "likes"

    lexeme = MorphTo("LexemeMedia", "likeable_type", "likeable_id")


class Lexeme(Model):
    __table__ = "articles"

    media = MorphMany("LexemeMedia", morph_key="likeable_type", morph_id="likeable_id")
    first_medium = MorphOne(first_medium, morph_key="likeable_type", morph_id="likeable_id")


class TestMorphNameEqualsClassName(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lexemes = [
            await Lexeme.create({"title": f"Lexeme {n}", "user_id": 1, "published_date": "2024-01-01 00:00:00"})
            for n in range(2)
        ]
        for lexeme in self.lexemes:
            for _ in range(2):
                await LexemeMedia.create({"likeable_type": "Lexeme", "likeable_id": lexeme.id})

    async def test_registry_uses_class_name_as_default_morph_name(self):
        self.assertEqual(Registry.get_morph_name(Lexeme), "Lexeme")
        self.assertEqual(Lexeme.media.get_record_key_lookup(self.lexemes[0]), "Lexeme")

    async def test_eager_load_morph_many_on_collection(self):
        lexemes = await Lexeme.with_("media").where_in("id", [lexeme.id for lexeme in self.lexemes]).get()

        self.assertEqual(len(lexemes), 2)
        for lexeme in lexemes:
            self.assertIsInstance(lexeme.media, Collection)
            self.assertEqual(len(lexeme.media), 2)
            self.assertTrue(all(medium.likeable_id == lexeme.id for medium in lexeme.media))

    async def test_eager_load_morph_many_on_first(self):
        lexeme = await Lexeme.with_("media").where("id", self.lexemes[0].id).first()

        self.assertEqual(len(lexeme.media), 2)

    async def test_lazy_load_morph_many(self):
        lexeme = await Lexeme.find(self.lexemes[1].id)
        await lexeme.load("media")

        self.assertEqual(len(lexeme.media), 2)
        self.assertTrue(all(medium.likeable_id == lexeme.id for medium in lexeme.media))

    async def test_eager_load_morph_one(self):
        lexemes = await Lexeme.with_("first_medium").where_in("id", [lexeme.id for lexeme in self.lexemes]).get()

        for lexeme in lexemes:
            self.assertIsInstance(lexeme.first_medium, LexemeMedia)
            self.assertEqual(lexeme.first_medium.likeable_id, lexeme.id)

    async def test_lazy_load_morph_one(self):
        lexeme = await Lexeme.find(self.lexemes[0].id)
        await lexeme.load("first_medium")

        self.assertIsInstance(lexeme.first_medium, LexemeMedia)
        self.assertEqual(lexeme.first_medium.likeable_id, lexeme.id)

    async def test_eager_load_morph_to(self):
        media = await LexemeMedia.with_("lexeme").where("likeable_type", "Lexeme").get()

        self.assertEqual(len(media), 4)
        for medium in media:
            self.assertIsInstance(medium.lexeme, Lexeme)
            self.assertEqual(medium.lexeme.id, medium.likeable_id)

    async def test_nested_eager_load_through_morph_one(self):
        lexemes = await Lexeme.with_("first_medium.lexeme").where_in("id", [lexeme.id for lexeme in self.lexemes]).get()

        for lexeme in lexemes:
            self.assertEqual(lexeme.first_medium.lexeme.id, lexeme.id)

    async def test_nested_eager_load(self):
        lexeme = await Lexeme.with_("media.lexeme").where("id", self.lexemes[0].id).first()

        self.assertEqual(len(lexeme.media), 2)
        self.assertTrue(all(medium.lexeme.id == lexeme.id for medium in lexeme.media))

from fastapi_startkit.masoniteorm import HasMany, Model

from ..test_case import TestCase


class Lexeme(Model):
    __table__ = "lexemes"
    __timestamps__ = False

    word: str
    base_lexeme_id: int | None

    examples: "Lexeme" = HasMany["Lexeme"](local_key="id", foreign_key="base_lexeme_id")


class TestNullableForeignKeyEagerLoad(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("lexemes") as table:
            table.increments("id")
            table.string("word")
            table.integer("base_lexeme_id").nullable()

        self.base = await Lexeme.create({"word": "run", "base_lexeme_id": None})
        await Lexeme.create({"word": "running", "base_lexeme_id": self.base.id})
        await Lexeme.create({"word": "ran", "base_lexeme_id": self.base.id})

    async def test_nullable_foreign_key_reads_back_as_int(self):
        running = await Lexeme.where("word", "running").first_or_fail()

        assert running.base_lexeme_id == self.base.id
        assert type(running.base_lexeme_id) is int

    async def test_null_foreign_key_stays_none(self):
        base = await Lexeme.where("word", "run").first_or_fail()

        assert base.base_lexeme_id is None

    async def test_eager_load_get_attaches_children(self):
        lexemes = await Lexeme.with_("examples").where_null("base_lexeme_id").get()

        assert sorted(example.word for example in lexemes[0].examples) == ["ran", "running"]

    async def test_eager_load_first_attaches_children(self):
        base = await Lexeme.with_("examples").where("word", "run").first_or_fail()

        assert sorted(example.word for example in base.examples) == ["ran", "running"]

    async def test_load_attaches_children(self):
        base = await Lexeme.where("word", "run").first_or_fail()
        await base.load("examples")

        assert sorted(example.word for example in base.examples) == ["ran", "running"]

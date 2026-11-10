from fastapi_startkit.masoniteorm import Model

from .fixtures.db import schema
from .test_case import TestCase


class PjArticle(Model):
    __table__ = "pj_articles"
    __timestamps__ = None
    __casts__ = {"settings": "json"}
    id: int
    title: str
    settings: dict


class TestPostgresJsonPathWhere(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await schema.drop_table_if_exists("pj_articles")
        async with await schema.create("pj_articles") as table:
            table.increments("id")
            table.string("title")
            table.jsonb("settings")
        for title, settings in [
            ("Paris", {"headline": "Life in Lyon", "meta": {"lang": "fr"}}),
            ("Lyon", {"headline": "A week in PARIS", "meta": {"lang": "en"}}),
            ("Nice", {"headline": "Beaches", "meta": {"lang": "fr"}}),
        ]:
            await PjArticle.create({"title": title, "settings": settings})

    async def asyncTearDown(self):
        await schema.drop_table_if_exists("pj_articles")
        await super().asyncTearDown()

    async def test_like_on_a_jsonb_key_is_case_insensitive(self):
        rows = await PjArticle.where("settings->headline", "like", "%paris%").get()
        self.assertEqual([row.title for row in rows], ["Lyon"])

    async def test_where_matches_a_nested_jsonb_key(self):
        rows = await PjArticle.where("settings->meta->lang", "fr").order_by("id").get()
        self.assertEqual([row.title for row in rows], ["Paris", "Nice"])

    async def test_or_where_combines_a_column_and_a_jsonb_key(self):
        rows = (
            await PjArticle.where("title", "like", "%paris%")
            .or_where("settings->headline", "like", "%paris%")
            .order_by("id")
            .get()
        )
        self.assertEqual([row.title for row in rows], ["Paris", "Lyon"])

    async def test_order_by_a_jsonb_key(self):
        rows = await PjArticle.order_by("settings->headline").get()
        self.assertEqual([row.title for row in rows], ["Lyon", "Nice", "Paris"])

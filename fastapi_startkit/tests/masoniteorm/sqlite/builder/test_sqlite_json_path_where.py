import json

from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class Article(Model):
    __table__ = "json_articles"
    __timestamps__ = None
    id: int
    title: str
    settings: str


class TestSqliteJsonPathWhere(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await DB.connection("default").execute(
            "CREATE TABLE json_articles (id INTEGER PRIMARY KEY, title TEXT, settings TEXT)"
        )
        for title, settings in [
            ("Paris", {"headline": "Life in Lyon", "meta": {"lang": "fr"}}),
            ("Lyon", {"headline": "A week in Paris", "meta": {"lang": "en"}}),
            ("Nice", {"headline": "Beaches", "meta": {"lang": "fr"}}),
        ]:
            await Article.create({"title": title, "settings": json.dumps(settings)})

    async def test_where_matches_a_json_key(self):
        rows = await Article.where("settings->headline", "like", "%Paris%").get()
        self.assertEqual([row.title for row in rows], ["Lyon"])

    async def test_where_matches_a_nested_json_key(self):
        rows = await Article.where("settings->meta->lang", "fr").order_by("id").get()
        self.assertEqual([row.title for row in rows], ["Paris", "Nice"])

    async def test_or_where_combines_a_column_and_a_json_key(self):
        rows = (
            await Article.where("title", "like", "%Paris%")
            .or_where("settings->headline", "like", "%Paris%")
            .order_by("id")
            .get()
        )
        self.assertEqual([row.title for row in rows], ["Paris", "Lyon"])

    async def test_a_quote_in_the_value_stays_a_binding(self):
        rows = await Article.where("settings->headline", "x' OR '1'='1").get()
        self.assertEqual(len(rows), 0)

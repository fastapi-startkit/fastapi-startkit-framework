from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class Category(Model):
    __table__ = "categories"
    __timestamps__ = None
    id: int
    name: str


class Post(Model):
    __table__ = "posts"
    __timestamps__ = None
    id: int
    title: str
    category_id: int


def category_name_subquery():
    """Correlated subquery selecting the parent category name for each post."""
    return Category.query().select("name").where_column("categories.id", "posts.category_id")


class TestSqliteOrderBySubquery(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        conn = DB.connection("default")
        await conn.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        await conn.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT, category_id INTEGER)")
        # Category ids deliberately NOT in alphabetical order, so ordering by the
        # correlated name subquery differs from ordering by id/category_id.
        await conn.execute("INSERT INTO categories (id, name) VALUES (1, 'Zebra'), (2, 'Apple'), (3, 'Mango')")
        await conn.execute(
            "INSERT INTO posts (id, title, category_id) VALUES (1, 'z', 1), (2, 'a', 2), (3, 'm', 3), (4, 'a2', 2)"
        )

    async def test_order_by_correlated_subquery(self):
        posts = await Post.query().order_by(category_name_subquery()).get()
        # Apple (ids 2,4) < Mango (3) < Zebra (1)
        self.assertEqual([p.title for p in posts], ["a", "a2", "m", "z"])

    async def test_order_by_correlated_subquery_desc(self):
        posts = await Post.query().order_by(category_name_subquery(), "desc").get()
        self.assertEqual([p.title for p in posts], ["z", "m", "a", "a2"])

    async def test_full_chain_order_by_subquery_then_paginate(self):
        page = await Post.query().order_by(category_name_subquery()).paginate(per_page=2, page=1)
        meta = page.serialize()["meta"]
        self.assertEqual(meta["total"], 4)
        self.assertEqual(meta["last_page"], 2)
        self.assertEqual(meta["current_page"], 1)
        self.assertEqual(meta["count"], 2)
        self.assertEqual(meta["next_page"], 2)
        self.assertIsNone(meta["previous_page"])
        self.assertEqual([d["title"] for d in page.serialize()["data"]], ["a", "a2"])

        page2 = await Post.query().order_by(category_name_subquery()).paginate(per_page=2, page=2)
        meta2 = page2.serialize()["meta"]
        self.assertEqual(meta2["current_page"], 2)
        self.assertEqual(meta2["previous_page"], 1)
        self.assertIsNone(meta2["next_page"])
        self.assertEqual([d["title"] for d in page2.serialize()["data"]], ["m", "z"])

    async def test_string_order_by_still_works(self):
        posts = await Post.query().order_by("id", "desc").get()
        self.assertEqual([p.id for p in posts], [4, 3, 2, 1])

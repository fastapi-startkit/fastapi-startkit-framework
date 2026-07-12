from fastapi_startkit.masoniteorm import Model

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
        async with await self.schema.create("categories") as table:
            table.id()
            table.string("name")
        async with await self.schema.create("posts") as table:
            table.id()
            table.string("title")
            table.integer("category_id")
        # Category ids deliberately NOT in alphabetical order, so ordering by the
        # correlated name subquery differs from ordering by id/category_id.
        await Category.query().insert(
            [{"id": 1, "name": "Zebra"}, {"id": 2, "name": "Apple"}, {"id": 3, "name": "Mango"}]
        )
        await Post.query().insert(
            [
                {"id": 1, "title": "z", "category_id": 1},
                {"id": 2, "title": "a", "category_id": 2},
                {"id": 3, "title": "m", "category_id": 3},
                {"id": 4, "title": "a2", "category_id": 2},
            ]
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

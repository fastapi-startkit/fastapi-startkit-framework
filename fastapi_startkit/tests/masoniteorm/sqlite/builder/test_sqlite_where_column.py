from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class Pair(Model):
    __table__ = "pairs"
    __timestamps__ = None
    id: int
    left_val: int
    right_val: int
    name: str
    nickname: str


class TestSqliteWhereColumn(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        conn = DB.connection("default")
        await conn.execute(
            "CREATE TABLE pairs (id INTEGER PRIMARY KEY, left_val INTEGER, right_val INTEGER, name TEXT, nickname TEXT)"
        )
        await conn.execute(
            "INSERT INTO pairs (id, left_val, right_val, name, nickname) VALUES "
            "(1, 5, 5, 'Sam', 'Sam'), "  # left == right, name == nickname
            "(2, 9, 3, 'Bob', 'Bobby'), "  # left > right, name != nickname
            "(3, 2, 8, 'Al', 'Al')"  # left < right, name == nickname
        )

    async def test_where_column_two_arg_equality(self):
        rows = await Pair.query().where_column("left_val", "right_val").order_by("id").get()
        self.assertEqual([p.id for p in rows], [1])

    async def test_where_column_three_arg_greater_than(self):
        rows = await Pair.query().where_column("left_val", ">", "right_val").order_by("id").get()
        self.assertEqual([p.id for p in rows], [2])

    async def test_where_column_three_arg_less_than(self):
        rows = await Pair.query().where_column("left_val", "<", "right_val").order_by("id").get()
        self.assertEqual([p.id for p in rows], [3])

    async def test_where_column_not_equal(self):
        rows = await Pair.query().where_column("name", "!=", "nickname").order_by("id").get()
        self.assertEqual([p.id for p in rows], [2])

    async def test_or_where_column_or_joined(self):
        # id == 3 OR left_val > right_val  ->  rows 2 (9>3) and 3 (id match)
        query = Pair.query().where("id", 3).or_where_column("left_val", ">", "right_val")
        self.assertIn("OR left_val > right_val", query.to_sql())
        rows = await query.order_by("id").get()
        self.assertEqual([p.id for p in rows], [2, 3])

    async def test_or_where_column_two_arg_equality(self):
        # left_val == right_val OR name == nickname  ->  rows 1 (both) and 3 (name==nick)
        rows = (
            await Pair.query()
            .where_column("left_val", "right_val")
            .or_where_column("name", "nickname")
            .order_by("id")
            .get()
        )
        self.assertEqual([p.id for p in rows], [1, 3])

    async def test_where_column_rejects_invalid_operator(self):
        with self.assertRaises(ValueError):
            Pair.query().where_column("left_val", "BAD", "right_val")

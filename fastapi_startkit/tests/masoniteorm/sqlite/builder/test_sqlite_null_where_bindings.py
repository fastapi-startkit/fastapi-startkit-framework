from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class Ticket(Model):
    __table__ = "tickets"
    __timestamps__ = None
    id: int
    closed_at: str
    created_at: str


class TestSqliteNullWhereBindings(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        conn = DB.connection("default")
        await conn.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, closed_at TEXT, created_at TEXT)")
        await conn.execute(
            "INSERT INTO tickets (id, closed_at, created_at) VALUES "
            "(1, '2026-02-01', '2026-01-15'), "
            "(2, NULL, '2026-01-20'), "
            "(3, '2025-12-01', '2025-11-30'), "
            "(4, '2026-03-01', '2026-02-10')"
        )

    async def test_where_not_null_then_date_filter(self):
        rows = (
            await Ticket.query()
            .where_not_null("closed_at")
            .where("created_at", ">=", "2026-01-01")
            .order_by("id")
            .get()
        )
        self.assertEqual([t.id for t in rows], [1, 4])

    async def test_where_null_then_date_filter(self):
        rows = await Ticket.query().where_null("closed_at").where("created_at", ">=", "2026-01-01").get()
        self.assertEqual([t.id for t in rows], [2])

    async def test_or_where_not_null_then_value_filter(self):
        rows = (
            await Ticket.query().where("id", 2).or_where_not_null("closed_at").where("id", "<", 4).order_by("id").get()
        )
        self.assertEqual([t.id for t in rows], [1, 2, 3])

from datetime import date, datetime

from fastapi_startkit.masoniteorm import Model

from .fixtures.db import schema
from .test_case import TestCase


class PgUnReview(Model):
    __table__ = "pg_un_reviews"
    __timestamps__ = None
    id: int
    user_id: int
    created_at: datetime


class PgUnMessage(Model):
    __table__ = "pg_un_messages"
    __timestamps__ = None
    id: int
    user_id: int
    created_at: datetime


class PgUnEvent(Model):
    __table__ = "pg_un_events"
    __timestamps__ = None


def local_days(query):
    return query.select("user_id").select_raw(
        "(created_at AT TIME ZONE 'UTC' AT TIME ZONE ?)::date AS day", ["Asia/Kathmandu"]
    )


class TestPostgresUnionFromSub(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await schema.create("pg_un_reviews") as table:
            table.id()
            table.integer("user_id")
            table.timestamp("created_at")
        async with await schema.create("pg_un_messages") as table:
            table.id()
            table.integer("user_id")
            table.timestamp("created_at")

        await PgUnReview.query().insert(
            [
                {"id": 1, "user_id": 1, "created_at": datetime(2026, 1, 1, 20)},
                {"id": 2, "user_id": 2, "created_at": datetime(2026, 1, 1, 9)},
            ]
        )
        await PgUnMessage.query().insert(
            [
                {"id": 1, "user_id": 1, "created_at": datetime(2026, 1, 1, 21)},
                {"id": 2, "user_id": 2, "created_at": datetime(2026, 1, 1, 10)},
            ]
        )

    async def test_distinct_learners_per_local_day_across_a_union(self):
        events = local_days(PgUnReview.query()).union_all(local_days(PgUnMessage.query()))
        rows = await (
            PgUnEvent.query()
            .from_sub(events, "events")
            .select("day")
            .add_select_raw("COUNT(DISTINCT user_id) AS learners")
            .group_by("day")
            .order_by("day")
            .get()
        )
        self.assertEqual(
            [(row.serialize()["day"], row.serialize()["learners"]) for row in rows],
            [(date(2026, 1, 1), 1), (date(2026, 1, 2), 1)],
        )

from fastapi_startkit.masoniteorm import Model

from ..test_case import TestCase


class UnReview(Model):
    __table__ = "un_reviews"
    __timestamps__ = None
    id: int
    user_id: int
    mode: str
    day: str


class UnPlay(Model):
    __table__ = "un_plays"
    __timestamps__ = None
    id: int
    user_id: int
    day: str


class UnEvent(Model):
    __table__ = "un_events"
    __timestamps__ = None
    user_id: int
    day: str


def listen_reviews():
    return UnReview.query().select("user_id", "day").where("mode", "listen")


def plays():
    return UnPlay.query().select("user_id", "day")


def listen_events():
    return listen_reviews().union_all(plays())


class TestSqliteUnionFromSub(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("un_reviews") as table:
            table.id()
            table.integer("user_id")
            table.string("mode")
            table.string("day")
        async with await self.schema.create("un_plays") as table:
            table.id()
            table.integer("user_id")
            table.string("day")

        await UnReview.query().insert(
            [
                {"id": 1, "user_id": 1, "mode": "listen", "day": "2026-01-01"},
                {"id": 2, "user_id": 2, "mode": "listen", "day": "2026-01-01"},
                {"id": 3, "user_id": 2, "mode": "speak", "day": "2026-01-02"},
            ]
        )
        await UnPlay.query().insert(
            [
                {"id": 1, "user_id": 1, "day": "2026-01-01"},
                {"id": 2, "user_id": 3, "day": "2026-01-02"},
                {"id": 3, "user_id": 1, "day": "2026-01-02"},
            ]
        )

    async def test_union_all_keeps_duplicate_rows(self):
        rows = await listen_events().get()
        self.assertEqual(
            sorted((row.user_id, row.day) for row in rows),
            [
                (1, "2026-01-01"),
                (1, "2026-01-01"),
                (1, "2026-01-02"),
                (2, "2026-01-01"),
                (3, "2026-01-02"),
            ],
        )

    async def test_union_drops_duplicate_rows(self):
        rows = await listen_reviews().union(plays()).get()
        self.assertEqual(
            sorted((row.user_id, row.day) for row in rows),
            [(1, "2026-01-01"), (1, "2026-01-02"), (2, "2026-01-01"), (3, "2026-01-02")],
        )

    async def test_count_covers_every_member_of_the_union(self):
        self.assertEqual(await listen_events().count(), 5)
        self.assertEqual(await listen_reviews().union(plays()).count(), 4)

    async def test_from_sub_groups_distinct_learners_per_day_across_the_union(self):
        rows = await (
            UnEvent.query()
            .from_sub(listen_events(), "events")
            .select("day")
            .select_raw("count(distinct user_id) as learners")
            .group_by("day")
            .order_by("day")
            .get()
        )
        self.assertEqual(
            [(row.day, row.serialize()["learners"]) for row in rows],
            [
                ("2026-01-01", 2),
                ("2026-01-02", 2),
            ],
        )

    async def test_bound_fragments_in_members_and_outer_query_line_up(self):
        def tagged(query, skill):
            return query.select("user_id").select_raw("? as skill", [skill])

        events = tagged(UnReview.query().where("mode", "speak"), "speak").union_all(
            tagged(UnPlay.query().where("day", "2026-01-02"), "listen")
        )
        rows = await (
            UnEvent.query()
            .from_sub(events, "events")
            .select("skill")
            .select_raw("count(distinct user_id) * ? as learners", [10])
            .where("user_id", ">", 1)
            .group_by("skill")
            .order_by("skill")
            .get()
        )
        self.assertEqual(
            [(row.serialize()["skill"], row.serialize()["learners"]) for row in rows],
            [
                ("listen", 10),
                ("speak", 10),
            ],
        )

    async def test_from_sub_paginates_over_the_subquery(self):
        paginator = await UnEvent.query().from_sub(listen_events(), "events").order_by("user_id").paginate(2, 1)
        self.assertEqual(paginator.total, 5)
        self.assertEqual([row.user_id for row in paginator.result], [1, 1])

    async def test_model_proxies_start_a_query(self):
        self.assertEqual(await UnEvent.from_sub(listen_events(), "events").count(), 5)
        self.assertEqual(await UnPlay.union_all(UnPlay.query()).count(), 6)
        self.assertEqual(await UnPlay.union(UnPlay.query()).count(), 3)

    async def test_paginate_pages_over_the_whole_union(self):
        first = await listen_events().paginate(2, 1)
        last = await listen_events().paginate(2, 3)
        self.assertEqual(first.total, 5)
        self.assertEqual([(row.user_id, row.day) for row in first.result], [(1, "2026-01-01"), (2, "2026-01-01")])
        self.assertEqual(last.total, 5)
        self.assertEqual([(row.user_id, row.day) for row in last.result], [(1, "2026-01-02")])

    async def test_simple_paginate_pages_over_the_whole_union(self):
        first = await listen_events().simple_paginate(2, 1)
        last = await listen_events().simple_paginate(2, 3)
        self.assertEqual([(row.user_id, row.day) for row in first.result], [(1, "2026-01-01"), (2, "2026-01-01")])
        self.assertEqual(first.next_page, 2)
        self.assertEqual([(row.user_id, row.day) for row in last.result], [(1, "2026-01-02")])
        self.assertIsNone(last.next_page)

    async def test_chunk_pages_over_the_whole_union(self):
        batches = [[(row.user_id, row.day) for row in batch] async for batch in listen_events().chunk(2)]
        self.assertEqual(
            batches,
            [
                [(1, "2026-01-01"), (2, "2026-01-01")],
                [(1, "2026-01-01"), (3, "2026-01-02")],
                [(1, "2026-01-02")],
            ],
        )

    async def test_chunk_by_id_pages_over_the_whole_union(self):
        def reviews():
            return UnReview.query().where("mode", "listen").union_all(UnReview.query().where("mode", "speak"))

        ascending = [[row.id for row in batch] async for batch in reviews().chunk_by_id(2)]
        descending = [[row.id for row in batch] async for batch in reviews().chunk_by_id_desc(2)]
        self.assertEqual(ascending, [[1, 2], [3]])
        self.assertEqual(descending, [[3, 2], [1]])

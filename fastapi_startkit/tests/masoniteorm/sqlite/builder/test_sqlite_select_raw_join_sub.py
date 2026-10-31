from ...fixtures.join_sub_listing import (
    WINDOW_END,
    WINDOW_START,
    DUE_FLOOR,
    Lexeme,
    create_listing_tables,
    due_subquery,
    due_subquery_sql,
    listing_query,
    listing_rows,
    seed_listing,
)
from ..test_case import TestCase

DUE_DAY = "MAX(MIN(memories.due_date), ?)"

EXPECTED_ROWS = [
    (1, "avoir", "2026-01-04", 2, "verified"),
    (3, "chat", "2026-01-04", 1, "rejected"),
    (2, "boire", "2026-01-10", 1, "unverified"),
]


class TestSqliteSelectRawJoinSub(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await create_listing_tables(self.schema)
        await seed_listing()

    async def test_select_raw_with_bindings_returns_the_raw_column(self):
        lexemes = await (
            Lexeme.query()
            .select("lexemes.id")
            .select_raw("CASE WHEN lexemes.language = ? THEN 'native' ELSE 'foreign' END AS origin", ["fr"])
            .order_by("lexemes.id")
            .get()
        )

        self.assertEqual(
            [(lexeme.id, lexeme.serialize()["origin"]) for lexeme in lexemes],
            [(1, "native"), (2, "native"), (3, "native"), (4, "foreign"), (5, "native")],
        )

    async def test_listing_with_builder_join_sub(self):
        lexemes = await listing_query(due_subquery(DUE_DAY)).get()

        self.assertEqual(listing_rows(lexemes), EXPECTED_ROWS)

    async def test_listing_with_raw_join_sub_and_bindings(self):
        query = listing_query(due_subquery_sql(DUE_DAY), (DUE_FLOOR, WINDOW_START, WINDOW_END))

        self.assertEqual(listing_rows(await query.get()), EXPECTED_ROWS)

    async def test_count_drops_raw_columns_and_keeps_join_bindings(self):
        query = listing_query(due_subquery(DUE_DAY))

        self.assertEqual(await query.count(), 3)
        self.assertEqual(listing_rows(await query.get()), EXPECTED_ROWS)

    async def test_paginate_counts_through_the_join_and_pages_results(self):
        first = await listing_query(due_subquery(DUE_DAY)).paginate(2, 1)
        second = await listing_query(due_subquery_sql(DUE_DAY), (DUE_FLOOR, WINDOW_START, WINDOW_END)).paginate(2, 2)

        self.assertEqual(first.total, 3)
        self.assertEqual(first.last_page, 2)
        self.assertEqual(listing_rows(first.result), EXPECTED_ROWS[:2])
        self.assertEqual(second.total, 3)
        self.assertEqual(listing_rows(second.result), EXPECTED_ROWS[2:])

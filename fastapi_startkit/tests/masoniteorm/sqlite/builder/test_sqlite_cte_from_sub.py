from fastapi_startkit.masoniteorm import BelongsTo, Model

from ..test_case import TestCase


class CsSite(Model):
    __table__ = "cs_sites"
    __timestamps__ = None
    id: int
    name: str


class CsPage(Model):
    __table__ = "cs_pages"
    __timestamps__ = None
    id: int
    site_id: int
    words: int

    site = BelongsTo["CsSite"](local_key="site_id", foreign_key="id")


def pages_per_site():
    return CsPage.select("site_id").select_raw("COUNT(*) AS pages, SUM(words) AS words").group_by("site_id")


class CteFromSubCases:
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("cs_sites") as table:
            table.id()
            table.string("name")
        async with await self.schema.create("cs_pages") as table:
            table.id()
            table.integer("site_id")
            table.integer("words")

        await CsSite.query().insert([{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}, {"id": 3, "name": "Gamma"}])
        await CsPage.query().insert(
            [
                {"id": 1, "site_id": 1, "words": 100},
                {"id": 2, "site_id": 1, "words": 50},
                {"id": 3, "site_id": 1, "words": 10},
                {"id": 4, "site_id": 2, "words": 70},
                {"id": 5, "site_id": 2, "words": 30},
                {"id": 6, "site_id": 3, "words": 5},
            ]
        )

    async def test_cte_joined_to_a_model_table(self):
        sites = await (
            CsSite.with_query("totals", pages_per_site())
            .join("totals", "totals.site_id", "=", "cs_sites.id")
            .select("cs_sites.name", "totals.pages", "totals.words")
            .where("totals.words", ">", 50)
            .order_by("cs_sites.id")
            .get()
        )

        self.assertEqual([(site.name, site.pages, site.words) for site in sites], [("Alpha", 3, 160), ("Beta", 2, 100)])

    async def test_cte_read_as_the_table_hydrates_models(self):
        pages = await (
            CsPage.query()
            .with_query("long_pages", CsPage.where("words", ">=", 50))
            .table("long_pages")
            .where("long_pages.site_id", 1)
            .order_by("long_pages.id")
            .get()
        )

        self.assertEqual([(page.id, page.words) for page in pages], [(1, 100), (2, 50)])
        self.assertIsInstance(pages.first(), CsPage)

    async def test_cte_read_inside_a_where_exists_subquery(self):
        busy = CsPage.select("site_id").group_by("site_id").having_raw("COUNT(*) >= ?", [2])
        query = CsSite.with_query("busy", busy)
        sites = await (
            query.where_exists(query.new().table("busy").where_column("busy.site_id", "cs_sites.id"))
            .order_by("id")
            .get()
        )

        self.assertEqual([site.name for site in sites], ["Alpha", "Beta"])

    async def test_from_sub_aggregates_a_grouped_query(self):
        row = await (
            CsPage.from_sub(pages_per_site(), "per_site")
            .select_raw("MAX(per_site.pages) AS most, SUM(per_site.words) AS words")
            .first()
        )

        self.assertEqual((row.most, row.words), (3, 265))

    async def test_aggregate_helpers_run_against_the_derived_table(self):
        query = CsPage.from_sub(pages_per_site(), "per_site").where("per_site.pages", ">=", 2)

        self.assertEqual(await query.count(), 2)
        self.assertEqual(await CsPage.from_sub(pages_per_site(), "per_site").max("words"), 160)

    async def test_from_sub_rows_hydrate_and_eager_load(self):
        pages = await (
            CsPage.from_sub(CsPage.where("words", ">", 20), "p")
            .with_("site")
            .where("p.site_id", "!=", 1)
            .order_by("p.id")
            .get()
        )

        self.assertEqual([(page.id, page.site.name) for page in pages], [(4, "Beta"), (5, "Beta")])

    async def test_from_sub_accepts_a_callable(self):
        pages = await (
            CsPage.from_sub(lambda sub: sub.table("cs_pages").where("words", "<", 20), "small")
            .order_by("small.id")
            .get()
        )

        self.assertEqual([page.id for page in pages], [3, 6])

    async def test_cte_feeds_a_from_sub(self):
        rows = await (
            CsSite.with_query("totals", pages_per_site())
            .from_sub(lambda sub: sub.table("totals").where("totals.pages", ">", 1), "busy")
            .select("busy.site_id", "busy.words")
            .order_by("busy.site_id")
            .get()
        )

        self.assertEqual([(row.site_id, row.words) for row in rows], [(1, 160), (2, 100)])

    async def test_bound_value_is_never_interpolated(self):
        payload = "x' OR '1'='1"
        rows = await CsPage.from_sub(CsPage.select_raw("CAST(? AS TEXT) AS label", [payload]).where("id", 1), "t").get()

        self.assertEqual([row.label for row in rows], [payload])

    async def test_paginate_over_a_derived_table(self):
        paginator = await CsPage.from_sub(CsPage.where("words", ">", 20), "p").order_by("p.id").paginate(2, 2)

        self.assertEqual(paginator.total, 4)
        self.assertEqual([page.id for page in paginator], [4, 5])

    async def test_paginate_over_a_cte(self):
        paginator = await (
            CsPage.query()
            .with_query("long_pages", CsPage.where("words", ">=", 30))
            .table("long_pages")
            .where("long_pages.words", "<", 100)
            .order_by("long_pages.id")
            .paginate(2, 1)
        )

        self.assertEqual(paginator.total, 3)
        self.assertEqual([page.id for page in paginator], [2, 4])

    async def test_grouped_paginate_over_a_derived_table(self):
        paginator = await (
            CsPage.from_sub(CsPage.where("words", ">", 5), "p")
            .select("p.site_id")
            .select_raw("COUNT(*) AS pages")
            .group_by("p.site_id")
            .having_raw("COUNT(*) >= ?", [2])
            .order_by("p.site_id")
            .paginate(1, 1)
        )

        self.assertEqual(paginator.total, 2)
        self.assertEqual([(row.site_id, row.pages) for row in paginator], [(1, 3)])


class TestSqliteCteFromSub(CteFromSubCases, TestCase):
    pass

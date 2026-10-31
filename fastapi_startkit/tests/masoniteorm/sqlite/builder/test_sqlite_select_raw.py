from fastapi_startkit.masoniteorm import BelongsTo, Model

from ..test_case import TestCase


class StSite(Model):
    __table__ = "st_sites"
    __timestamps__ = None
    id: int
    name: str


class StPage(Model):
    __table__ = "st_pages"
    __timestamps__ = None
    id: int
    site_id: int
    words: int

    site = BelongsTo["StSite"](local_key="site_id", foreign_key="id")


class StUserPage(Model):
    __table__ = "st_user_pages"
    __timestamps__ = None
    id: int
    user_id: int
    page_id: int
    last_opened_at: str


class TestSqliteSelectRaw(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("st_sites") as table:
            table.id()
            table.string("name")
        async with await self.schema.create("st_pages") as table:
            table.id()
            table.integer("site_id")
            table.integer("words")
        async with await self.schema.create("st_user_pages") as table:
            table.id()
            table.integer("user_id")
            table.integer("page_id")
            table.string("last_opened_at")

        await StSite.query().insert([{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}, {"id": 3, "name": "Gamma"}])
        await StPage.query().insert(
            [
                {"id": 1, "site_id": 1, "words": 100},
                {"id": 2, "site_id": 1, "words": 50},
                {"id": 3, "site_id": 1, "words": 10},
                {"id": 4, "site_id": 2, "words": 70},
                {"id": 5, "site_id": 2, "words": 30},
                {"id": 6, "site_id": 3, "words": 5},
            ]
        )
        await StUserPage.query().insert(
            [
                {"id": 1, "user_id": 1, "page_id": 1, "last_opened_at": "2026-10-20"},
                {"id": 2, "user_id": 2, "page_id": 2, "last_opened_at": "2026-10-25"},
                {"id": 3, "user_id": 1, "page_id": 4, "last_opened_at": "2026-10-26"},
                {"id": 4, "user_id": 2, "page_id": 5, "last_opened_at": "2026-09-01"},
                {"id": 5, "user_id": 3, "page_id": 6, "last_opened_at": "2026-08-01"},
            ]
        )

    async def test_grouped_page_counts(self):
        pages = await StPage.query().select("site_id").select_raw("COUNT(*) AS pages").group_by("site_id").get()

        self.assertEqual(sorted((page.site_id, page.pages) for page in pages), [(1, 3), (2, 2), (3, 1)])

    async def test_grouped_opens_since_with_join(self):
        since = "2026-10-01"
        rows = await (
            StUserPage.query()
            .join("st_pages", "st_pages.id", "=", "st_user_pages.page_id")
            .where("st_user_pages.last_opened_at", ">=", since)
            .select("st_pages.site_id")
            .select_raw("COUNT(*) AS opens")
            .group_by("st_pages.site_id")
            .get()
        )

        self.assertEqual(sorted((row.site_id, row.opens) for row in rows), [(1, 2), (2, 1)])

    async def test_aggregates_with_bound_parameters(self):
        rows = await (
            StPage.select("site_id")
            .select_raw("SUM(words) AS total_words, SUM(CASE WHEN words >= ? THEN 1 ELSE 0 END) AS long_pages", [50])
            .group_by("site_id")
            .order_by("site_id")
            .get()
        )

        self.assertEqual(
            [(row.site_id, row.total_words, row.long_pages) for row in rows],
            [(1, 160, 2), (2, 100, 1), (3, 5, 0)],
        )

    async def test_bound_value_is_never_interpolated(self):
        rows = await StPage.select_raw("? AS label", ["x' OR '1'='1"]).where("id", 1).get()

        self.assertEqual(rows[0].label, "x' OR '1'='1")

    async def test_having_raw_filters_groups(self):
        rows = await (
            StPage.select("site_id")
            .select_raw("COUNT(*) AS pages")
            .group_by("site_id")
            .having_raw("COUNT(*) >= ?", [2])
            .having_raw("SUM(words) > ?", [100])
            .get()
        )

        self.assertEqual([(row.site_id, row.pages) for row in rows], [(1, 3)])

    async def test_having_raw_class_method(self):
        rows = await StPage.having_raw("COUNT(*) > ?", [2]).select("site_id").group_by("site_id").get()

        self.assertEqual([row.site_id for row in rows], [1])

    async def test_add_select_raw_keeps_model_columns(self):
        page = await StPage.add_select_raw("words * ? AS doubled", [2]).where("id", 2).first()

        self.assertEqual((page.id, page.site_id, page.words, page.doubled), (2, 1, 50, 100))

    async def test_eager_load_on_grouped_rows(self):
        rows = await (
            StPage.with_("site")
            .select("site_id")
            .select_raw("COUNT(*) AS pages")
            .group_by("site_id")
            .order_by("site_id")
            .get()
        )

        self.assertEqual([(row.site.name, row.pages) for row in rows], [("Alpha", 3), ("Beta", 2), ("Gamma", 1)])

    async def test_paginate_counts_groups(self):
        paginator = await (
            StPage.select("site_id")
            .select_raw("COUNT(*) AS pages")
            .where("words", ">", 0)
            .group_by("site_id")
            .order_by("site_id")
            .paginate(2, 1)
        )

        self.assertEqual(paginator.total, 3)
        self.assertEqual(paginator.last_page, 2)
        self.assertEqual([(row.site_id, row.pages) for row in paginator], [(1, 3), (2, 2)])

    async def test_paginate_counts_groups_left_by_having_with_bindings(self):
        paginator = await (
            StPage.select("site_id")
            .select_raw("SUM(words) * ? AS weighted", [2])
            .group_by("site_id")
            .having_raw("COUNT(*) >= ?", [2])
            .order_by("site_id")
            .paginate(1, 2)
        )

        self.assertEqual(paginator.total, 2)
        self.assertEqual([(row.site_id, row.weighted) for row in paginator], [(2, 200)])

    async def test_paginate_grouped_rows_on_an_aliased_table(self):
        paginator = await (
            StPage.query()
            .table("st_pages", "p")
            .add_select_raw("COUNT(*) AS pages")
            .where("p.words", ">", 20)
            .group_by("p.site_id")
            .having_raw("COUNT(*) >= ?", [2])
            .paginate(5, 1)
        )

        self.assertEqual(paginator.total, 2)
        self.assertEqual(sorted((row.site_id, row.pages) for row in paginator), [(1, 2), (2, 2)])

    async def test_paginate_on_an_aliased_table_without_grouping(self):
        paginator = await StPage.query().table("st_pages", "p").where("p.words", ">", 20).paginate(10, 1)

        self.assertEqual(paginator.total, 4)

    async def test_paginate_without_grouping_counts_rows(self):
        paginator = await StPage.select_raw("words * ? AS doubled", [2]).paginate(4, 1)

        self.assertEqual(paginator.total, 6)
        self.assertEqual(len(paginator.result), 4)

    async def test_simple_paginate_grouped_rows(self):
        paginator = await (
            StPage.select("site_id")
            .select_raw("COUNT(*) AS pages")
            .group_by("site_id")
            .order_by("site_id")
            .simple_paginate(2, 2)
        )

        self.assertEqual([(row.site_id, row.pages) for row in paginator], [(3, 1)])
        self.assertIsNone(paginator.next_page)

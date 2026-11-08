from fastapi_startkit.masoniteorm import HasMany, Model

from ..test_case import TestCase


class SqUser(Model):
    __table__ = "sq_users"
    __timestamps__ = None
    id: int
    name: str
    country: str

    orders = HasMany["SqOrder"](local_key="id", foreign_key="user_id")


class SqOrder(Model):
    __table__ = "sq_orders"
    __timestamps__ = None
    id: int
    user_id: int
    status: str
    total: int


class SqBan(Model):
    __table__ = "sq_bans"
    __timestamps__ = None
    id: int
    user_id: int
    active: int


def orders_of_user():
    return SqOrder.query().where_column("sq_orders.user_id", "sq_users.id")


class TestSqliteSubqueryWhere(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("sq_users") as table:
            table.id()
            table.string("name")
            table.string("country")
        async with await self.schema.create("sq_orders") as table:
            table.id()
            table.integer("user_id")
            table.string("status")
            table.integer("total")
        async with await self.schema.create("sq_bans") as table:
            table.id()
            table.integer("user_id")
            table.integer("active")

        await SqUser.query().insert(
            [
                {"id": 1, "name": "Ana", "country": "NP"},
                {"id": 2, "name": "Bo", "country": "NP"},
                {"id": 3, "name": "Cy", "country": "US"},
                {"id": 4, "name": "Di", "country": "US"},
                {"id": 5, "name": "Ed", "country": "US"},
            ]
        )
        await SqOrder.query().insert(
            [
                {"id": 1, "user_id": 1, "status": "paid", "total": 500},
                {"id": 2, "user_id": 1, "status": "open", "total": 20},
                {"id": 3, "user_id": 2, "status": "open", "total": 900},
                {"id": 4, "user_id": 3, "status": "paid", "total": 40},
                {"id": 5, "user_id": 5, "status": "paid", "total": 300},
            ]
        )
        await SqBan.query().insert(
            [
                {"id": 1, "user_id": 5, "active": 1},
                {"id": 2, "user_id": 2, "active": 0},
            ]
        )

    async def test_where_in_a_subquery(self):
        users = await SqUser.where_in("id", SqOrder.select("user_id").where("status", "paid")).order_by("id").get()

        self.assertEqual([user.id for user in users], [1, 3, 5])

    async def test_where_in_a_callable_subquery(self):
        users = await (
            SqUser.where_in("id", lambda sub: sub.table("sq_orders").select("user_id").where("total", ">", 400))
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in users], [1, 2])

    async def test_where_not_in_a_subquery(self):
        users = await SqUser.where_not_in("id", SqBan.select("user_id").where("active", 1)).order_by("id").get()

        self.assertEqual([user.id for user in users], [1, 2, 3, 4])

    async def test_where_not_exists_correlated(self):
        users = await SqUser.where_not_exists(orders_of_user()).get()

        self.assertEqual([user.id for user in users], [4])

    async def test_or_where_not_exists(self):
        users = await (
            SqUser.where("country", "NP")
            .or_where_not_exists(orders_of_user().where("sq_orders.status", "paid"))
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in users], [1, 2, 4])

    async def test_not_exists_and_exists_inside_nested_where_groups(self):
        users = await (
            SqUser.where(
                lambda group: group.where_exists(
                    orders_of_user().where("sq_orders.total", ">=", 500)
                ).or_where_not_exists(orders_of_user())
            )
            .where(
                lambda group: group.where_not_exists(
                    SqBan.query().where_column("sq_bans.user_id", "sq_users.id")
                ).where(
                    lambda inner: inner.where("country", "US").or_where_exists(
                        orders_of_user().where("sq_orders.status", "paid")
                    )
                )
            )
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in users], [1, 4])

    async def test_where_exists_accepts_a_callable(self):
        users = await (
            SqUser.query()
            .where_exists(lambda sub: sub.table("sq_bans").where_column("sq_bans.user_id", "sq_users.id"))
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in users], [2, 5])

    async def test_add_select_exists_flags_each_row(self):
        users = await (
            SqUser.add_select_exists("has_big_order", orders_of_user().where("sq_orders.total", ">=", 300))
            .order_by("id")
            .get()
        )

        self.assertEqual(
            [(user.id, user.name, user.has_big_order) for user in users],
            [(1, "Ana", 1), (2, "Bo", 1), (3, "Cy", 0), (4, "Di", 0), (5, "Ed", 1)],
        )

    async def test_bound_value_is_never_interpolated(self):
        injection = "paid' OR '1'='1"
        users = await SqUser.where_in("id", SqOrder.select("user_id").where("status", injection)).get()
        flagged = await SqUser.add_select_exists("hit", orders_of_user().where("sq_orders.status", injection)).get()

        self.assertEqual(len(users), 0)
        self.assertEqual({user.hit for user in flagged}, {0})

    async def test_combined_with_grouping_and_pagination(self):
        paginator = await (
            SqUser.select("country")
            .select_raw("COUNT(*) AS users")
            .where_in("id", SqOrder.select("user_id").where("total", ">", 10))
            .where_not_exists(SqBan.query().where_column("sq_bans.user_id", "sq_users.id").where("sq_bans.active", 1))
            .group_by("country")
            .having_raw("COUNT(*) >= ?", [1])
            .order_by("country")
            .paginate(1, 2)
        )

        self.assertEqual(paginator.total, 2)
        self.assertEqual([(row.country, row.users) for row in paginator], [("US", 1)])

    async def test_paginate_counts_rows_filtered_by_subqueries(self):
        paginator = await (
            SqUser.add_select_exists("has_paid", orders_of_user().where("sq_orders.status", "paid"))
            .where_not_in("id", SqBan.select("user_id").where("active", 1))
            .order_by("id")
            .paginate(2, 1)
        )

        self.assertEqual(paginator.total, 4)
        self.assertEqual([(user.id, user.has_paid) for user in paginator], [(1, 1), (2, 0)])

    async def test_eager_loads_rows_filtered_by_subqueries(self):
        users = await (
            SqUser.with_("orders")
            .where_in("id", SqOrder.select("user_id").where("status", "open"))
            .where_not_exists(SqBan.query().where_column("sq_bans.user_id", "sq_users.id"))
            .get()
        )

        self.assertEqual([(user.id, sorted(order.id for order in user.orders)) for user in users], [(1, [1, 2])])

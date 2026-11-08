from fastapi_startkit.masoniteorm import Model

from .fixtures.db import schema
from .test_case import TestCase


class PgSqUser(Model):
    __table__ = "pg_sq_users"
    __timestamps__ = None
    id: int
    name: str
    country: str


class PgSqOrder(Model):
    __table__ = "pg_sq_orders"
    __timestamps__ = None
    id: int
    user_id: int
    status: str
    total: int


def orders_of_user():
    return PgSqOrder.query().where_column("pg_sq_orders.user_id", "pg_sq_users.id")


class TestPostgresSubqueryWhere(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await schema.create("pg_sq_users") as table:
            table.id()
            table.string("name")
            table.string("country")
        async with await schema.create("pg_sq_orders") as table:
            table.id()
            table.integer("user_id")
            table.string("status")
            table.integer("total")

        await PgSqUser.query().insert(
            [
                {"id": 1, "name": "Ana", "country": "NP"},
                {"id": 2, "name": "Bo", "country": "NP"},
                {"id": 3, "name": "Cy", "country": "US"},
            ]
        )
        await PgSqOrder.query().insert(
            [
                {"id": 1, "user_id": 1, "status": "paid", "total": 500},
                {"id": 2, "user_id": 2, "status": "open", "total": 20},
            ]
        )

    async def test_where_in_and_not_in_a_subquery(self):
        paid = await PgSqUser.where_in("id", PgSqOrder.select("user_id").where("status", "paid")).get()
        unpaid = await (
            PgSqUser.where_not_in("id", lambda sub: sub.table("pg_sq_orders").select("user_id").where("status", "paid"))
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in paid], [1])
        self.assertEqual([user.id for user in unpaid], [2, 3])

    async def test_where_not_exists_correlated(self):
        users = await PgSqUser.where("country", "NP").or_where_not_exists(orders_of_user()).order_by("id").get()

        self.assertEqual([user.id for user in users], [1, 2, 3])
        self.assertEqual([user.id for user in await PgSqUser.where_not_exists(orders_of_user()).get()], [3])

    async def test_not_exists_and_exists_inside_nested_where_groups(self):
        users = await (
            PgSqUser.where(
                lambda group: group.where_exists(orders_of_user()).where(
                    lambda inner: inner.where_not_exists(
                        orders_of_user().where("pg_sq_orders.status", "paid")
                    ).or_where_exists(orders_of_user().where("pg_sq_orders.total", ">=", 500))
                )
            )
            .order_by("id")
            .get()
        )

        self.assertEqual([user.id for user in users], [1, 2])

    async def test_add_select_exists_returns_booleans(self):
        users = await (
            PgSqUser.add_select_exists("has_big_order", orders_of_user().where("pg_sq_orders.total", ">", 100))
            .where("country", "NP")
            .order_by("id")
            .get()
        )

        self.assertEqual([(user.id, user.has_big_order) for user in users], [(1, True), (2, False)])

    async def test_grouped_pagination_keeps_binding_order(self):
        paginator = await (
            PgSqUser.select("country")
            .select_raw("COUNT(*) AS users")
            .add_select_exists("flag", lambda sub: sub.table("pg_sq_orders").where("total", ">", 1000))
            .where_in("id", PgSqOrder.select("user_id").where("total", ">", 10))
            .group_by("country")
            .having_raw("COUNT(*) >= ?", [1])
            .paginate(5, 1)
        )

        self.assertEqual(paginator.total, 1)
        self.assertEqual([(row.country, row.users, row.flag) for row in paginator], [("NP", 2, False)])

from decimal import Decimal

from fastapi_startkit.masoniteorm import Model
from ..test_case import TestCase


class PricedItem(Model):
    __table__ = "priced_items"

    name: str
    price: Decimal
    discount: Decimal | None


class TestSqliteDecimal(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("priced_items") as table:
            table.id()
            table.string("name")
            table.decimal("price", 10, 2)
            table.decimal("discount", 10, 2, nullable=True)
            table.timestamps()

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("priced_items")
        await super().asyncTearDown()

    async def test_create_and_read_back_decimal(self):
        item = await PricedItem.create({"name": "Pen", "price": Decimal("19.99")})

        fetched = await PricedItem.find(item.id)

        self.assertEqual(fetched.price, Decimal("19.99"))
        self.assertIsInstance(fetched.price, Decimal)
        self.assertIsNone(fetched.discount)

    async def test_update_decimal(self):
        item = await PricedItem.create({"name": "Pen", "price": Decimal("1.10")})

        await item.update({"price": Decimal("2.25")})

        self.assertEqual((await PricedItem.find(item.id)).price, Decimal("2.25"))

    async def test_where_with_decimal_binding(self):
        await PricedItem.create({"name": "Pen", "price": Decimal("3.50")})

        found = await PricedItem.where("price", Decimal("3.50")).first()

        self.assertEqual(found.name, "Pen")

    async def test_raw_connection_binds_decimal(self):
        connection = self.db.connection("default")
        await connection.insert('INSERT INTO "priced_items" ("name", "price") VALUES (?, ?)', ["Raw", Decimal("4.75")])

        rows = await connection.select('SELECT "name" FROM "priced_items" WHERE "price" = ?', [Decimal("4.75")])

        self.assertEqual([row["name"] for row in rows], ["Raw"])

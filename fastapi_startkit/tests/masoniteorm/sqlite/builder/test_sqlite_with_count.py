from ...fixtures.model import IncomingShipment, Product, Store, User
from ..fixtures.db import DB
from ..test_case import TestCase


class TestSqliteWithCount(TestCase):
    """End-to-end with_count() across every relationship type on seeded data.

    Seeder gives: user Joe (id 1) with 1 article + 1 logo (through the article);
    user Jane (id 2) with none. This suite adds store/product pivot rows for the
    BelongsToMany case and reuses the seeded ports/shipments for HasOneThrough.
    """

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await Store.query().insert([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
        await Product.query().insert([{"id": 2, "name": "Gadget"}, {"id": 3, "name": "Gizmo"}])
        # store 1 -> products 1 & 2; store 2 -> none
        await (
            DB.connection("default")
            .query()
            .table("product_store")
            .insert([{"id": 1, "store_id": 1, "product_id": 1}, {"id": 2, "store_id": 1, "product_id": 2}])
        )

    async def test_has_many_count(self):
        users = await User.query().with_count("articles").order_by("id").get()
        self.assertEqual({u.id: u.serialize()["articles_count"] for u in users}, {1: 1, 2: 0})

    async def test_has_many_count_seeds_base_columns(self):
        # with_count on an unselected query must still return the owner's columns.
        user = (await User.query().with_count("articles").where("id", 1).get()).first()
        self.assertEqual(user.name, "Joe")
        self.assertEqual(user.serialize()["articles_count"], 1)

    async def test_has_many_count_with_callback_constraint(self):
        users = (
            await User.query().with_count("articles", lambda q: q.where("title", "Masonite ORM")).order_by("id").get()
        )
        self.assertEqual({u.id: u.serialize()["articles_count"] for u in users}, {1: 1, 2: 0})

    async def test_has_many_count_with_callback_excluding_all(self):
        users = (
            await User.query().with_count("articles", lambda q: q.where("title", "does-not-exist")).order_by("id").get()
        )
        self.assertEqual({u.id: u.serialize()["articles_count"] for u in users}, {1: 0, 2: 0})

    async def test_has_many_through_count(self):
        users = await User.query().with_count("logos").order_by("id").get()
        self.assertEqual({u.id: u.serialize()["logos_count"] for u in users}, {1: 1, 2: 0})

    async def test_belongs_to_many_count(self):
        stores = await Store.query().with_count("products").order_by("id").get()
        self.assertEqual({s.id: s.serialize()["products_count"] for s in stores}, {1: 2, 2: 0})

    async def test_has_one_through_count(self):
        # Every seeded shipment routes through a port that maps to exactly one country.
        ships = await IncomingShipment.query().with_count("from_country").get()
        counts = [s.serialize()["from_country_count"] for s in ships]
        self.assertEqual(len(ships), 7)
        self.assertTrue(all(c == 1 for c in counts))

    async def test_with_count_model_classmethod(self):
        users = await User.with_count("articles").order_by("id").get()
        self.assertEqual({u.id: u.serialize()["articles_count"] for u in users}, {1: 1, 2: 0})

    async def test_with_count_sql_is_a_correlated_subquery(self):
        sql = User.query().with_count("articles").to_sql()
        self.assertIn("SELECT COUNT(*) FROM", sql)
        self.assertIn("articles.user_id = users.id", sql)
        self.assertIn("AS articles_count", sql)

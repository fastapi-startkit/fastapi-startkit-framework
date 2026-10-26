from fastapi_startkit.masoniteorm.collection import Collection
from ...fixtures.model import Product, Store
from ..test_case import TestCase


class TestBelongsToManyRelationship(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.store = await Store.create({"name": "Test Store"})
        self.product1 = await Product.create({"name": "Widget"})
        self.product2 = await Product.create({"name": "Gadget"})

    async def test_attach_creates_pivot_record(self):
        await Store.products.attach(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        products = store.products
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "Widget")

    async def test_attach_multiple_products(self):
        await Store.products.attach(self.store, self.product1)
        await Store.products.attach(self.store, self.product2)
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        products = store.products
        self.assertEqual(len(products), 2)

    async def test_detach_removes_pivot_record(self):
        await Store.products.attach(self.store, self.product1)
        await Store.products.attach(self.store, self.product2)
        await Store.products.detach(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        products = store.products
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "Gadget")

    async def test_eager_load_belongs_to_many(self):
        await Store.products.attach(self.store, self.product1)
        stores = await Store.with_("products").get()
        store = stores.where("id", self.store.id).first()
        self.assertIsNotNone(store)
        self.assertEqual(len(store.products), 1)

    async def test_eager_load_empty_relationship(self):
        stores = await Store.with_("products").get()
        store = stores.where("id", self.store.id).first()
        self.assertIsNotNone(store)
        self.assertTrue(store.products.is_empty())

    async def test_eager_load_first_empty_relationship(self):
        store = await Store.with_("products").where("id", self.store.id).first()
        self.assertIsInstance(store.products, Collection)
        self.assertTrue(store.products.is_empty())

    async def test_load_empty_relationship(self):
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        self.assertIsInstance(store.products, Collection)
        self.assertTrue(store.products.is_empty())

    async def test_pivot_access_after_eager_load(self):
        await Store.products.attach(self.store, self.product1)
        stores = await Store.with_("products").get()
        store = stores.where("id", self.store.id).first()
        product = store.products[0]
        pivot = product.pivot
        self.assertIsNotNone(pivot)

    async def test_with_timestamps_in_pivot(self):
        # Store.products uses with_timestamps=True
        await Store.products.attach(self.store, self.product1)
        stores = await Store.with_("products").get()
        store = stores.where("id", self.store.id).first()
        product = store.products[0]
        self.assertIsNotNone(product.pivot)

    async def test_explicit_table_relationship(self):
        # Store.products_table uses table="product_table"
        await Store.products_table.attach(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        await store.load("products_table")
        products = store.products_table
        self.assertEqual(len(products), 1)

    async def test_attach_related_creates_pivot_record(self):
        await Store.products.attach_related(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        products = store.products
        self.assertEqual(len(products), 1)

    async def test_detach_related_removes_pivot_record(self):
        await Store.products.attach_related(self.store, self.product1)
        await Store.products.detach_related(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        await store.load("products")
        products = store.products
        self.assertEqual(len(products), 0)

    async def test_get_pivot_table_name(self):
        # Test the helper method directly using builder proxies
        rel = Store.products
        # Manually set the pivot table name to test the method
        rel._table = None
        name = rel.get_pivot_table_name(self.store.get_builder(), self.product1.get_builder())
        self.assertEqual(name, "product_store")

    async def test_map_related_returns_result(self):
        results = [self.product1, self.product2]
        rel = Store.products
        mapped = rel.map_related(results)
        self.assertEqual(mapped, results)

    async def test_register_related_groups_by_owner_key(self):
        await Store.products.attach(self.store, self.product1)
        stores = await Store.with_("products").get()
        store = stores.where("id", self.store.id).first()
        # If register_related works, the products collection is populated
        self.assertEqual(len(store.products), 1)

    async def test_query_has_filters_stores_with_products(self):
        store2 = await Store.create({"name": "Empty Store"})
        await Store.products.attach(self.store, self.product1)

        stores_with_products = await Store.where_has("products").get()
        store_ids = [s.id for s in stores_with_products]

        self.assertIn(self.store.id, store_ids)
        self.assertNotIn(store2.id, store_ids)

    async def test_query_has_returns_builder(self):
        # query_has should add a where_exists clause to the builder
        builder = Store.query()
        result = Store.products.query_has(builder, method="where_exists")
        # The builder has a where clause appended (we just verify no error is raised)
        self.assertIsNotNone(builder)


class TestBelongsToManyWhereHas(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.downtown = await Store.create({"name": "Downtown"})
        self.uptown = await Store.create({"name": "Uptown"})
        self.empty = await Store.create({"name": "Empty"})
        self.widget = await Product.create({"name": "Widget"})
        self.gadget = await Product.create({"name": "Gadget"})
        await Store.products.attach(self.downtown, self.widget)
        await Store.products.attach(self.uptown, self.gadget)

    async def names(self, query):
        return sorted(store.name for store in await query.get())

    def scoped(self):
        return Store.where_in("id", [self.downtown.id, self.uptown.id, self.empty.id])

    async def test_where_has_without_callback(self):
        self.assertEqual(await self.names(self.scoped().where_has("products")), ["Downtown", "Uptown"])

    async def test_where_has_with_query_callback(self):
        query = self.scoped().where_has("products", lambda q: q.where("name", "Widget"))
        self.assertEqual(await self.names(query), ["Downtown"])

    async def test_where_has_with_query_callback_matching_nothing(self):
        query = self.scoped().where_has("products", lambda q: q.where("name", "Missing"))
        self.assertEqual(await self.names(query), [])

    async def test_where_has_with_callback_returning_none(self):
        def only_gadgets(q):
            q.where("name", "Gadget")

        self.assertEqual(await self.names(self.scoped().where_has("products", only_gadgets)), ["Uptown"])

    async def test_where_has_with_id_list_callback(self):
        query = self.scoped().where_has("products", lambda q: [self.gadget.id])
        self.assertEqual(await self.names(query), ["Uptown"])

    async def test_or_where_has_with_query_callback(self):
        query = Store.where("name", "Empty").or_where_has("products", lambda q: q.where("name", "Gadget"))
        self.assertEqual(await self.names(query), ["Empty", "Uptown"])

    async def test_or_where_has_without_callback(self):
        query = Store.where("name", "Empty").or_where_has("products")
        self.assertEqual(await self.names(query), ["Downtown", "Empty", "Uptown"])

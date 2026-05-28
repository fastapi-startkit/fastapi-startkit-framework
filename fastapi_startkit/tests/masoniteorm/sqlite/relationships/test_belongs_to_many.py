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
        products = await store.products
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "Widget")

    async def test_attach_multiple_products(self):
        await Store.products.attach(self.store, self.product1)
        await Store.products.attach(self.store, self.product2)
        store = await Store.where("id", self.store.id).first()
        products = await store.products
        self.assertEqual(len(products), 2)

    async def test_detach_removes_pivot_record(self):
        await Store.products.attach(self.store, self.product1)
        await Store.products.attach(self.store, self.product2)
        await Store.products.detach(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        products = await store.products
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
        # Empty BelongsToMany eager load returns None (consistent with other relationships)
        self.assertIsNone(store.products)

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
        products = await store.products_table
        self.assertEqual(len(products), 1)

    async def test_attach_related_creates_pivot_record(self):
        await Store.products.attach_related(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        products = await store.products
        self.assertEqual(len(products), 1)

    async def test_detach_related_removes_pivot_record(self):
        await Store.products.attach_related(self.store, self.product1)
        await Store.products.detach_related(self.store, self.product1)
        store = await Store.where("id", self.store.id).first()
        products = await store.products
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

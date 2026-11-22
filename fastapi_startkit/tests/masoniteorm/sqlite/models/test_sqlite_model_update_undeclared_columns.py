from ...fixtures.model import Articles, Product
from ..test_case import TestCase


class TestUpdateUndeclaredColumns(TestCase):
    async def test_update_persists_column_not_declared_on_model(self):
        article = await Articles.first()

        await article.update({"title": "Renamed"})

        self.assertEqual(article.title, "Renamed")
        self.assertEqual((await Articles.find(article.id)).title, "Renamed")

    async def test_update_persists_on_model_without_declared_columns(self):
        product = await Product.first()

        await product.update({"name": "Gadget"})

        self.assertEqual((await Product.find(product.id)).name, "Gadget")

    async def test_update_or_create_updates_existing_record_with_undeclared_column(self):
        article = await Articles.first()

        await Articles.update_or_create({"id": article.id}, {"title": "Upserted"})

        self.assertEqual((await Articles.find(article.id)).title, "Upserted")
        self.assertEqual(await Articles.count(), 1)

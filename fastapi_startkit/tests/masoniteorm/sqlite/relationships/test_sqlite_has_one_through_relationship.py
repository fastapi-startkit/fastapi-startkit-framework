from ...fixtures.model import Country, IncomingShipment
from ..test_case import TestCase


class TestHasOneThroughRelationship(TestCase):
    async def test_has_one_through_can_eager_load(self):
        shipments = await IncomingShipment.where("name", "Bread").with_("from_country").get()
        assert shipments.count() == 2

        shipment1 = shipments.shift()
        assert isinstance(shipment1.from_country, Country)
        assert shipment1.from_country.country_id == 20

        shipment2 = shipments.shift()
        assert isinstance(shipment2.from_country, Country)
        assert shipment2.from_country.country_id == 40

        # check .first() and .get() produce the same result
        single = await IncomingShipment.where("name", "Tractor Parts").with_("from_country").first()
        single_get = await IncomingShipment.where("name", "Tractor Parts").with_("from_country").get()
        assert single.from_country.country_id == 10
        assert single_get.count() == 1
        assert single.from_country.country_id == single_get.first().from_country.country_id

    async def test_has_one_through_eager_load_can_be_empty(self):
        shipments = await (
            IncomingShipment.where("name", "Bread")
            .where_has("from_country", lambda query: query.where("name", "Uruguay"))
            .with_("from_country")
            .get()
        )
        assert shipments.count() == 0

    async def test_has_one_through_can_get_related(self):
        shipment = await IncomingShipment.where("name", "Milk").first()
        country = await shipment.from_country
        assert isinstance(country, Country)
        assert country.country_id == 10

    async def test_has_one_through_has_query(self):
        shipments = await IncomingShipment.where_has("from_country", lambda query: query.where("name", "USA")).get()
        assert shipments.count() == 2

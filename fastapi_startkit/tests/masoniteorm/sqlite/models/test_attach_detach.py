from fastapi_startkit.masoniteorm.models.model import Model
from fastapi_startkit.masoniteorm import HasOne, BelongsTo
from ..test_case import TestCase


class Bottle(Model):
    __table__ = "bottles"
    __timestamps__ = False

    lid: "BottleLid" = HasOne("BottleLid", "bottle_id", "id")


class BottleLid(Model):
    __table__ = "bottle_lids"
    __timestamps__ = False

    colour: str
    bottle_id: int | None
    bottle: "Bottle" = BelongsTo("Bottle", "id", "bottle_id")


class TestAttachDetach(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("bottles") as table:
            table.integer("id").primary()
            table.string("label")
        async with await self.schema.create_table_if_not_exists("bottle_lids") as table:
            table.integer("id").primary()
            table.string("colour")
            table.integer("bottle_id", nullable=True)

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("bottle_lids")
        await self.schema.drop_table_if_exists("bottles")
        await super().asyncTearDown()

    async def test_has_one_attach(self):
        bottle = await Bottle.create({"label": "cola"})
        lid = await BottleLid.create({"colour": "Red"})

        # Attach using the relationship descriptor (access on class returns the descriptor)
        updated_lid = await Bottle.lid.attach(bottle, lid)
        assert updated_lid is not None

        # Reload lid and verify foreign key was set
        refreshed = await BottleLid.where("id", lid.id).first()
        assert int(refreshed.bottle_id) == bottle.id

    async def test_has_one_detach(self):
        bottle = await Bottle.create({"label": "milk"})
        lid = await BottleLid.create({"colour": "Blue"})

        # Attach first
        await Bottle.lid.attach(bottle, lid)

        # Now detach
        await Bottle.lid.detach(bottle, lid)

        refreshed = await BottleLid.where("id", lid.id).first()
        assert refreshed.bottle_id is None

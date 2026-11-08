import datetime
from typing import Optional, Union

import pendulum

from fastapi_startkit.masoniteorm import Model

from ..test_case import TestCase


class Measurement(Model):
    __table__ = "measurements"
    __timestamps__ = False

    quantity: int | None
    ratio: Optional[float]
    active: Union[bool, None]
    taken_at: datetime.datetime | None
    meta: dict | None


class TestSqliteNullableCasts(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("measurements") as table:
            table.increments("id")
            table.integer("quantity").nullable()
            table.float("ratio").nullable()
            table.boolean("active").nullable()
            table.datetime("taken_at").nullable()
            table.json("meta").nullable()

    async def test_values_round_trip_with_their_python_type(self):
        created = await Measurement.create(
            {
                "quantity": 3,
                "ratio": 0.5,
                "active": False,
                "taken_at": "2026-10-31 08:00:00",
                "meta": {"unit": "cm"},
            }
        )

        measurement = await Measurement.find_or_fail(created.id)

        assert type(measurement.quantity) is int and measurement.quantity == 3
        assert type(measurement.ratio) is float and measurement.ratio == 0.5
        assert measurement.active is False
        assert isinstance(measurement.taken_at, pendulum.DateTime)
        assert measurement.taken_at == pendulum.datetime(2026, 10, 31, 8)
        assert measurement.meta == {"unit": "cm"}

    async def test_nulls_round_trip_as_none(self):
        created = await Measurement.create(
            {"quantity": None, "ratio": None, "active": None, "taken_at": None, "meta": None}
        )

        measurement = await Measurement.find_or_fail(created.id)

        assert measurement.quantity is None
        assert measurement.ratio is None
        assert measurement.active is None
        assert measurement.taken_at is None
        assert measurement.meta is None

    async def test_nulls_are_written_as_sql_null(self):
        created = await Measurement.create({"quantity": None, "active": None, "meta": None})

        row = (
            await Measurement.where("id", created.id)
            .where_null("quantity")
            .where_null("active")
            .where_null("meta")
            .first()
        )

        assert row is not None

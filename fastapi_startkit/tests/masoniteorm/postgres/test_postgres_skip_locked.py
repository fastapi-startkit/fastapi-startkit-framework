import asyncio
import contextlib

from fastapi_startkit.masoniteorm import Model

from .fixtures.db import DB, schema
from .test_case import TestCase

BLOCKED_FOR = 0.3
SETTLES_WITHIN = 5


class PskQueueItem(Model):
    __table__ = "psk_queue_items"
    __timestamps__ = None
    id: int
    status: str


def pending(batch):
    return PskQueueItem.where("status", "pending").order_by("id").limit(batch)


class TestPostgresSkipLocked(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.release = asyncio.Event()
        self.holders = []
        await schema.drop_table_if_exists("psk_queue_items")
        async with await schema.create("psk_queue_items") as table:
            table.increments("id")
            table.string("status")
        await PskQueueItem.query().insert([{"status": "pending"} for _ in range(5)])

    async def asyncTearDown(self):
        self.release.set()
        for task in self.holders:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(task, SETTLES_WITHIN)
        await schema.drop_table_if_exists("psk_queue_items")
        await super().asyncTearDown()

    async def claim_and_hold(self, batch, lock):
        claimed = asyncio.get_running_loop().create_future()

        async def worker():
            async with DB.connection().transaction():
                ids = []
                for item in await lock(pending(batch)).get():
                    await PskQueueItem.where("id", item.id).update({"status": "processing"})
                    ids.append(item.id)
                claimed.set_result(ids)
                await self.release.wait()

        self.holders.append(asyncio.ensure_future(worker()))
        return claimed

    async def test_concurrent_claims_skip_each_others_rows(self):
        def skip_locked(query):
            return query.lock("FOR UPDATE SKIP LOCKED")

        first = await asyncio.wait_for(await self.claim_and_hold(2, skip_locked), SETTLES_WITHIN)
        second = await asyncio.wait_for(await self.claim_and_hold(2, skip_locked), SETTLES_WITHIN)
        third = await asyncio.wait_for(await self.claim_and_hold(2, skip_locked), SETTLES_WITHIN)

        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)
        self.assertEqual(len(third), 1)
        self.assertEqual(len(set(first) | set(second) | set(third)), 5)

        self.release.set()
        await asyncio.gather(*self.holders)
        self.assertEqual(await PskQueueItem.where("status", "processing").count(), 5)

    async def test_a_plain_update_lock_waits_for_the_holder(self):
        def skip_locked(query):
            return query.lock("FOR UPDATE SKIP LOCKED")

        held = await asyncio.wait_for(await self.claim_and_hold(1, skip_locked), SETTLES_WITHIN)
        blocked = await self.claim_and_hold(1, lambda query: query.lock())

        done, _ = await asyncio.wait({blocked}, timeout=BLOCKED_FOR)
        self.assertEqual(done, set())
        self.release.set()
        self.assertNotIn(held[0], await asyncio.wait_for(blocked, SETTLES_WITHIN))

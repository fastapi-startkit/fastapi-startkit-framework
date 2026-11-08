import asyncio
import contextlib

from fastapi_startkit.masoniteorm import Model

from .fixtures.db import DB, schema
from .test_case import TestCase

BLOCKED_FOR = 0.3
SETTLES_WITHIN = 5


class PlOwner(Model):
    __table__ = "pl_owners"
    __timestamps__ = None
    id: int
    name: str


class PlAccount(Model):
    __table__ = "pl_accounts"
    __timestamps__ = None
    id: int
    owner_id: int


def first_owner(lock):
    return lambda: lock(PlOwner.where("id", 1)).first()


def update_lock(query):
    return query.lock_for_update()


def share_lock(query):
    return query.shared_lock()


class TestPostgresLock(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.release = asyncio.Event()
        self.holders = []
        await self.drop_tables()
        async with await schema.create("pl_owners") as table:
            table.increments("id")
            table.string("name")
        async with await schema.create("pl_accounts") as table:
            table.increments("id")
            table.integer("owner_id")
            table.foreign("owner_id").references("id").on("pl_owners")
        await PlOwner.query().insert({"id": 1, "name": "Ada"})

    async def asyncTearDown(self):
        self.release.set()
        for task in self.holders:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await asyncio.wait_for(task, SETTLES_WITHIN)
        await self.drop_tables()
        await super().asyncTearDown()

    @staticmethod
    async def drop_tables():
        await schema.drop_table_if_exists("pl_accounts")
        await schema.drop_table_if_exists("pl_owners")

    async def hold(self, take_lock, then=None):
        held = asyncio.Event()

        async def holder():
            async with DB.connection().transaction():
                await take_lock()
                held.set()
                await self.release.wait()
                if then is not None:
                    await then()

        self.holders.append(asyncio.ensure_future(holder()))
        await asyncio.wait_for(held.wait(), SETTLES_WITHIN)

    async def in_transaction(self, read):
        async with DB.connection().transaction():
            return (await read()).name

    def start(self, read):
        task = asyncio.ensure_future(self.in_transaction(read))
        self.holders.append(task)
        return task

    async def assert_blocked_until_release(self, read):
        waiter = self.start(read)
        done, _ = await asyncio.wait({waiter}, timeout=BLOCKED_FOR)
        self.assertEqual(done, set())
        self.release.set()
        return await asyncio.wait_for(waiter, SETTLES_WITHIN)

    async def test_lock_for_update_waits_for_the_holder_and_reads_its_commit(self):
        await self.hold(
            first_owner(update_lock),
            then=lambda: PlOwner.where("id", 1).update({"name": "Grace"}),
        )

        self.assertEqual(await asyncio.wait_for(self.start(first_owner(lambda q: q)), SETTLES_WITHIN), "Ada")
        self.assertEqual(await self.assert_blocked_until_release(first_owner(update_lock)), "Grace")

    async def test_lock_for_update_waits_for_an_in_flight_child_insert(self):
        await self.hold(lambda: PlAccount.query().insert({"owner_id": 1}))

        self.assertEqual(await self.assert_blocked_until_release(first_owner(update_lock)), "Ada")
        self.assertEqual(await PlAccount.where("owner_id", 1).count(), 1)

    async def test_shared_locks_share_and_block_lock_for_update(self):
        await self.hold(first_owner(share_lock))

        self.assertEqual(await asyncio.wait_for(self.start(first_owner(share_lock)), SETTLES_WITHIN), "Ada")
        self.assertEqual(await self.assert_blocked_until_release(first_owner(update_lock)), "Ada")

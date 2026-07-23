"""
Tests for Laravel-style chunk(), chunk_by_id() and chunk_by_id_desc() on the
async QueryBuilder and their Model classmethod entry points.

A dedicated ``chunk_items`` table (ids 1..10, odd ids active) is created and
seeded on top of the shared sqlite TestCase so the batching maths stay simple
and deterministic. The seeded ``countries`` table (country_id 10/20/30/40 on
the ``dev`` connection) exercises keyset paging on a non-``id`` primary key.
"""

from fastapi_startkit.masoniteorm import Model
from tests.masoniteorm.fixtures.model import Country
from tests.masoniteorm.sqlite.test_case import TestCase


class ChunkItem(Model):
    __table__ = "chunk_items"
    __timestamps__ = False

    id: int
    name: str
    active: bool


class ChunkTestCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.schema.drop_table_if_exists("chunk_items")
        async with await self.schema.on("default").create("chunk_items") as table:
            table.id()
            table.string("name")
            table.boolean("active").default(True)
        await ChunkItem.query().insert([{"name": f"Item {i}", "active": i % 2 == 1} for i in range(1, 11)])

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("chunk_items")
        await super().asyncTearDown()


class TestChunk(ChunkTestCase):
    async def test_yields_batches_covering_all_rows(self):
        batches = []
        async for batch in ChunkItem.chunk(3):
            batches.append(batch)

        self.assertEqual([len(b) for b in batches], [3, 3, 3, 1])
        ids = [item.id for batch in batches for item in batch]
        self.assertEqual(ids, list(range(1, 11)))

    async def test_batches_are_collections_of_hydrated_models(self):
        async for batch in ChunkItem.chunk(4):
            self.assertIsInstance(batch, ChunkItem().new_collection([]).__class__)
            self.assertTrue(all(isinstance(item, ChunkItem) for item in batch))
            break

    async def test_exact_multiple_does_not_loop_forever(self):
        batches = [len(b) async for b in ChunkItem.chunk(5)]
        self.assertEqual(batches, [5, 5])

    async def test_chainable_after_where(self):
        ids = []
        async for batch in ChunkItem.where("active", True).chunk(2):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, [1, 3, 5, 7, 9])

    async def test_empty_result_yields_nothing(self):
        batches = [b async for b in ChunkItem.where("id", ">", 100).chunk(3)]
        self.assertEqual(batches, [])

    async def test_size_zero_raises(self):
        with self.assertRaises(ValueError):
            async for _ in ChunkItem.chunk(0):
                pass

    async def test_negative_size_raises(self):
        with self.assertRaises(ValueError):
            async for _ in ChunkItem.chunk(-1):
                pass


class TestChunkById(ChunkTestCase):
    async def test_yields_all_rows_ordered_by_id(self):
        ids = []
        async for batch in ChunkItem.chunk_by_id(3):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, list(range(1, 11)))

    async def test_batches_are_collections_of_hydrated_models(self):
        async for batch in ChunkItem.chunk_by_id(4):
            self.assertIsInstance(batch, ChunkItem().new_collection([]).__class__)
            self.assertTrue(all(isinstance(item, ChunkItem) for item in batch))
            break

    async def test_chainable_after_where(self):
        ids = []
        async for batch in ChunkItem.where("active", True).chunk_by_id(2):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, [1, 3, 5, 7, 9])

    async def test_custom_column_on_non_id_primary_key(self):
        ids = []
        async for batch in Country.chunk_by_id(2, column="country_id"):
            ids.extend(c.country_id for c in batch)
        self.assertEqual(ids, [10, 20, 30, 40])

    async def test_safe_when_rows_deleted_mid_iteration(self):
        seen = []
        async for batch in ChunkItem.chunk_by_id(2):
            seen.extend(item.id for item in batch)
            # Delete a not-yet-seen row to prove keyset paging never skips.
            await ChunkItem.where("id", batch.last().id + 1).delete()
        # 1,2 -> del 3; 4,5 -> del 6; 7,8 -> del 9; 10
        self.assertEqual(seen, [1, 2, 4, 5, 7, 8, 10])

    async def test_respects_existing_limit(self):
        batches = []
        async for batch in ChunkItem.limit(4).chunk_by_id(3):
            batches.append([item.id for item in batch])
        # limit(4) chunked by 3 -> 3 + 1
        self.assertEqual(batches, [[1, 2, 3], [4]])

    async def test_respects_existing_offset(self):
        ids = []
        async for batch in ChunkItem.offset(2).chunk_by_id(3):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, [3, 4, 5, 6, 7, 8, 9, 10])

    async def test_missing_alias_column_raises(self):
        with self.assertRaises(RuntimeError):
            async for _ in ChunkItem.select("name").chunk_by_id(3, alias="id"):
                pass

    async def test_alias_reads_last_seen_from_given_column(self):
        ids = []
        async for batch in ChunkItem.chunk_by_id(4, column="id", alias="id"):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, list(range(1, 11)))

    async def test_size_zero_raises(self):
        with self.assertRaises(ValueError):
            async for _ in ChunkItem.chunk_by_id(0):
                pass


class TestChunkByIdDesc(ChunkTestCase):
    async def test_yields_all_rows_in_descending_id_order(self):
        ids = []
        async for batch in ChunkItem.chunk_by_id_desc(3):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, list(range(10, 0, -1)))

    async def test_batch_sizes(self):
        batches = [len(b) async for b in ChunkItem.chunk_by_id_desc(3)]
        self.assertEqual(batches, [3, 3, 3, 1])

    async def test_chainable_after_where(self):
        ids = []
        async for batch in ChunkItem.where("active", True).chunk_by_id_desc(2):
            ids.extend(item.id for item in batch)
        self.assertEqual(ids, [9, 7, 5, 3, 1])

    async def test_safe_when_rows_deleted_mid_iteration(self):
        seen = []
        async for batch in ChunkItem.chunk_by_id_desc(2):
            seen.extend(item.id for item in batch)
            # Delete the next lower, not-yet-seen row.
            await ChunkItem.where("id", batch.last().id - 1).delete()
        # 10,9 -> del 8; 7,6 -> del 5; 4,3 -> del 2; 1
        self.assertEqual(seen, [10, 9, 7, 6, 4, 3, 1])

    async def test_size_zero_raises(self):
        with self.assertRaises(ValueError):
            async for _ in ChunkItem.chunk_by_id_desc(0):
                pass

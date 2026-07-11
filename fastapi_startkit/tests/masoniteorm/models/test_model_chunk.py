"""
Tests for Laravel-style chunk() and chunk_by_id() on the async QueryBuilder
and their Model classmethod entry points.

All tests run against an in-memory SQLite database so they are
self-contained and require no external services.
"""

import pytest

from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.model import Model

SQLITE_CONFIG = {
    "default": "sqlite",
    "connections": {
        "sqlite": {
            "driver": "sqlite",
            "url": "sqlite+aiosqlite:///:memory:",
        },
    },
}


@pytest.fixture
async def db():
    manager = DatabaseManager(ConnectionFactory(), SQLITE_CONFIG)
    yield manager
    await manager.clear()


@pytest.fixture
def ProjectModel(db):
    class Project(Model):
        id: int
        name: str
        active: bool

    Project.db_manager = db
    return Project


@pytest.fixture
async def projects_table(db, ProjectModel):
    schema = db.get_schema_builder()
    await schema.drop_table_if_exists("projects")
    async with await schema.on("default").create("projects") as table:
        table.id()
        table.string("name")
        table.boolean("active").default(True)
        table.timestamps()
    yield schema
    await schema.drop_table_if_exists("projects")


@pytest.fixture
async def seeded_projects(ProjectModel, projects_table):
    """Insert 10 projects (ids 1..10); even-numbered ones are inactive."""
    await ProjectModel.query().insert([{"name": f"Project {i}", "active": i % 2 == 1} for i in range(1, 11)])
    return ProjectModel


# ---------------------------------------------------------------------------
# chunk()
# ---------------------------------------------------------------------------


class TestChunk:
    async def test_yields_batches_covering_all_rows(self, ProjectModel, seeded_projects):
        batches = []
        async for batch in ProjectModel.chunk(3):
            batches.append(batch)

        assert [len(b) for b in batches] == [3, 3, 3, 1]
        ids = [p.id for batch in batches for p in batch]
        assert ids == list(range(1, 11))

    async def test_batches_are_collections_of_hydrated_models(self, ProjectModel, seeded_projects):
        async for batch in ProjectModel.chunk(4):
            assert isinstance(batch, ProjectModel().new_collection([]).__class__)
            assert all(isinstance(p, ProjectModel) for p in batch)
            break

    async def test_exact_multiple_does_not_loop_forever(self, ProjectModel, seeded_projects):
        batches = [b async for b in ProjectModel.chunk(5)]
        assert [len(b) for b in batches] == [5, 5]

    async def test_chainable_after_where(self, ProjectModel, seeded_projects):
        ids = []
        async for batch in ProjectModel.where("active", True).chunk(2):
            ids.extend(p.id for p in batch)
        assert ids == [1, 3, 5, 7, 9]

    async def test_empty_table_yields_nothing(self, ProjectModel, projects_table):
        batches = [b async for b in ProjectModel.chunk(3)]
        assert batches == []

    async def test_size_zero_raises(self, ProjectModel, seeded_projects):
        with pytest.raises(ValueError):
            async for _ in ProjectModel.chunk(0):
                pass

    async def test_negative_size_raises(self, ProjectModel, seeded_projects):
        with pytest.raises(ValueError):
            async for _ in ProjectModel.chunk(-1):
                pass


# ---------------------------------------------------------------------------
# chunk_by_id()
# ---------------------------------------------------------------------------


class TestChunkById:
    async def test_yields_all_rows_ordered_by_id(self, ProjectModel, seeded_projects):
        ids = []
        async for batch in ProjectModel.chunk_by_id(3):
            ids.extend(p.id for p in batch)
        assert ids == list(range(1, 11))

    async def test_batches_are_collections_of_hydrated_models(self, ProjectModel, seeded_projects):
        async for batch in ProjectModel.chunk_by_id(4):
            assert isinstance(batch, ProjectModel().new_collection([]).__class__)
            assert all(isinstance(p, ProjectModel) for p in batch)
            break

    async def test_chainable_after_where(self, ProjectModel, seeded_projects):
        ids = []
        async for batch in ProjectModel.where("active", True).chunk_by_id(2):
            ids.extend(p.id for p in batch)
        assert ids == [1, 3, 5, 7, 9]

    async def test_custom_column(self, ProjectModel, seeded_projects):
        ids = []
        async for batch in ProjectModel.chunk_by_id(4, column="id"):
            ids.extend(p.id for p in batch)
        assert ids == list(range(1, 11))

    async def test_safe_when_rows_deleted_mid_iteration(self, ProjectModel, seeded_projects):
        seen = []
        async for batch in ProjectModel.chunk_by_id(2):
            seen.extend(p.id for p in batch)
            # Delete a not-yet-seen row to prove keyset pagination doesn't skip.
            await ProjectModel.where("id", batch.last().id + 1).delete()
        # ids 1,2 -> delete 3; 4,5 -> delete 6; 7,8 -> delete 9; 10
        assert seen == [1, 2, 4, 5, 7, 8, 10]

    async def test_empty_table_yields_nothing(self, ProjectModel, projects_table):
        batches = [b async for b in ProjectModel.chunk_by_id(3)]
        assert batches == []

    async def test_size_zero_raises(self, ProjectModel, seeded_projects):
        with pytest.raises(ValueError):
            async for _ in ProjectModel.chunk_by_id(0):
                pass

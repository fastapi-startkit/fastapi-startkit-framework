"""Tests for ORM Seeder (task #16).

Tests the Seeder class without needing a live database.
"""

from unittest.mock import patch

import pytest

from fastapi_startkit.masoniteorm.seeds.Seeder import Seeder


# ---------------------------------------------------------------------------
# Minimal seeder stubs for testing
# ---------------------------------------------------------------------------


class FirstSeeder:
    call_order = []

    def __init__(self, connection=None):
        self.connection = connection

    async def run(self):
        FirstSeeder.call_order.append("first")


class SecondSeeder:
    call_order = []

    def __init__(self, connection=None):
        self.connection = connection

    async def run(self):
        SecondSeeder.call_order.append("second")


# ---------------------------------------------------------------------------
# Seeder.call — ordering and tracking
# ---------------------------------------------------------------------------


class TestSeederCall:
    @pytest.mark.asyncio
    async def test_call_runs_each_seeder(self):
        order = []

        class SeedA:
            def __init__(self, connection=None):
                pass

            async def run(self):
                order.append("A")

        class SeedB:
            def __init__(self, connection=None):
                pass

            async def run(self):
                order.append("B")

        seeder = Seeder()
        await seeder.call(SeedA, SeedB)

        assert order == ["A", "B"]

    @pytest.mark.asyncio
    async def test_call_tracks_ran_seeds(self):
        class SeedC:
            def __init__(self, connection=None):
                pass

            async def run(self):
                pass

        seeder = Seeder()
        await seeder.call(SeedC)

        assert SeedC in seeder.ran_seeds

    @pytest.mark.asyncio
    async def test_call_multiple_seeders_all_tracked(self):
        class S1:
            def __init__(self, connection=None):
                pass

            async def run(self):
                pass

        class S2:
            def __init__(self, connection=None):
                pass

            async def run(self):
                pass

        seeder = Seeder()
        await seeder.call(S1, S2)

        assert S1 in seeder.ran_seeds
        assert S2 in seeder.ran_seeds
        assert len(seeder.ran_seeds) == 2

    @pytest.mark.asyncio
    async def test_call_preserves_registration_order(self):
        order = []

        class First:
            def __init__(self, connection=None):
                pass

            async def run(self):
                order.append(1)

        class Second:
            def __init__(self, connection=None):
                pass

            async def run(self):
                order.append(2)

        class Third:
            def __init__(self, connection=None):
                pass

            async def run(self):
                order.append(3)

        seeder = Seeder()
        await seeder.call(First, Second, Third)

        assert order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_call_with_no_seeders_does_nothing(self):
        seeder = Seeder()
        await seeder.call()
        assert seeder.ran_seeds == []

    @pytest.mark.asyncio
    async def test_seeder_passes_connection_to_child(self):
        received_connection = []

        class CheckConnection:
            def __init__(self, connection=None):
                received_connection.append(connection)

            async def run(self):
                pass

        seeder = Seeder(connection="my_conn")
        await seeder.call(CheckConnection)

        assert received_connection == ["my_conn"]


# ---------------------------------------------------------------------------
# Seeder attributes
# ---------------------------------------------------------------------------


class TestSeederAttributes:
    def test_default_seed_path(self):
        seeder = Seeder()
        assert seeder.seed_path == "databases/seeds"

    def test_custom_seed_path(self):
        seeder = Seeder(seed_path="custom/seeds")
        assert seeder.seed_path == "custom/seeds"

    def test_seed_module_converts_slashes_to_dots(self):
        seeder = Seeder(seed_path="databases/seeds")
        assert seeder.seed_module == "databases.seeds"

    def test_seed_module_backslash(self):
        seeder = Seeder(seed_path="databases\\seeds")
        assert seeder.seed_module == "databases.seeds"

    def test_initial_ran_seeds_is_empty(self):
        seeder = Seeder()
        assert seeder.ran_seeds == []

    def test_connection_stored(self):
        seeder = Seeder(connection="postgres")
        assert seeder.connection == "postgres"


# ---------------------------------------------------------------------------
# Seeder.run_database_seed — via pydoc.locate (mocked)
# ---------------------------------------------------------------------------


class TestSeederRunDatabaseSeed:
    @pytest.mark.asyncio
    async def test_run_database_seed_raises_when_not_found(self):
        seeder = Seeder(seed_path="nonexistent.path")
        with pytest.raises(ValueError, match="Could not find the DatabaseSeeder"):
            await seeder.run_database_seed()

    @pytest.mark.asyncio
    async def test_run_database_seed_calls_run(self):
        ran = []

        class FakeDatabaseSeeder:
            def __init__(self, connection=None):
                pass

            async def run(self):
                ran.append(True)

        seeder = Seeder()

        with patch("fastapi_startkit.masoniteorm.seeds.Seeder.pydoc.locate", return_value=FakeDatabaseSeeder):
            await seeder.run_database_seed()

        assert ran == [True]
        assert FakeDatabaseSeeder in seeder.ran_seeds

    @pytest.mark.asyncio
    async def test_run_specific_seed_raises_when_not_found(self):
        seeder = Seeder()
        with pytest.raises(ValueError, match="Could not find the"):
            await seeder.run_specific_seed("NonExistentSeeder")

    @pytest.mark.asyncio
    async def test_run_specific_seed_calls_run(self):
        ran = []

        class SpecificSeeder:
            def __init__(self, connection=None):
                pass

            async def run(self):
                ran.append("specific")

        seeder = Seeder()

        with patch("fastapi_startkit.masoniteorm.seeds.Seeder.pydoc.locate", return_value=SpecificSeeder):
            await seeder.run_specific_seed("SpecificSeeder")

        assert ran == ["specific"]
        assert SpecificSeeder in seeder.ran_seeds

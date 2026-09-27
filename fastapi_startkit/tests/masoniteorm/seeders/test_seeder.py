import pytest

from fastapi_startkit.masoniteorm.seeders import Seeder

from .fixtures.seeders.database_seeder import DatabaseSeeder
from .fixtures.seeders.first_seeder import FirstSeeder
from .fixtures.seeders.recorder import CALLS
from .fixtures.seeders.sample_seeder import SampleSeeder
from .fixtures.seeders.second_seeder import SecondSeeder

FIXTURE_SEED_PATH = "tests.masoniteorm.seeders.fixtures.seeders"


@pytest.fixture(autouse=True)
def reset_recorder():
    CALLS.clear()
    yield
    CALLS.clear()


def test_seed_module_replaces_forward_slashes_with_dots():
    seeder = Seeder(seed_path="databases/seeders")

    assert seeder.seed_module == "databases.seeders"


def test_seed_module_replaces_backslashes_with_dots():
    seeder = Seeder(seed_path="databases\\seeders")

    assert seeder.seed_module == "databases.seeders"


def test_defaults_have_no_ran_seeds():
    seeder = Seeder()

    assert seeder.ran_seeds == []
    assert seeder.connection is None


async def test_call_runs_seeders_in_order_with_connection():
    seeder = Seeder(connection="sqlite")

    await seeder.call(FirstSeeder, SecondSeeder)

    assert CALLS == [("first", "sqlite"), ("second", "sqlite")]
    assert seeder.ran_seeds == [FirstSeeder, SecondSeeder]


async def test_call_appends_to_ran_seeds_for_each_invocation():
    seeder = Seeder()

    await seeder.call(FirstSeeder)
    await seeder.call(SecondSeeder)

    assert seeder.ran_seeds == [FirstSeeder, SecondSeeder]


async def test_run_database_seed_locates_and_runs_database_seeder():
    seeder = Seeder(seed_path=FIXTURE_SEED_PATH, connection="sqlite")

    await seeder.run_database_seed()

    assert CALLS == [
        ("database_seeder_start", "sqlite"),
        ("first", "sqlite"),
        ("second", "sqlite"),
    ]
    assert seeder.ran_seeds == [DatabaseSeeder]


async def test_run_database_seed_raises_when_module_missing():
    seeder = Seeder(seed_path="tests.masoniteorm.seeders.fixtures.does_not_exist")

    with pytest.raises(ValueError, match="Could not find the DatabaseSeeder class"):
        await seeder.run_database_seed()


async def test_run_specific_seed_locates_and_runs_seeder():
    seeder = Seeder(seed_path=FIXTURE_SEED_PATH, connection="sqlite")

    await seeder.run_specific_seed("sample_seeder.SampleSeeder")

    assert CALLS == [("sample", "sqlite")]
    assert seeder.ran_seeds == [SampleSeeder]


async def test_run_specific_seed_raises_when_missing():
    seeder = Seeder(seed_path=FIXTURE_SEED_PATH)

    with pytest.raises(ValueError, match="Could not find the .* seeder file"):
        await seeder.run_specific_seed("does_not_exist.NopeSeeder")

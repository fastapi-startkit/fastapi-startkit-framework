from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi_startkit.masoniteorm.testing.transaction import DatabaseTransaction, RefreshDatabase

from ..fixtures.model import User
from .test_case import TestCase


class TestDatabaseTransactionHarness(TestCase):
    async def test_start_and_stop_roll_back_writes(self):
        harness = DatabaseTransaction()
        await harness.asyncStartTestRun()
        try:
            await User.create({"email": "harness@example.com", "name": "Harness", "is_admin": False})
            assert await User.where("email", "harness@example.com").first() is not None
        finally:
            await harness.asyncStopTestRun()
        assert await User.where("email", "harness@example.com").first() is None


class TestRefreshDatabaseMigrate(TestCase):
    async def test_migrate_database_runs_fresh_once_with_string_directory(self):
        application = MagicMock()
        application.use_base_path.return_value = Path("/project/databases/migrations")
        migrator = MagicMock()
        migrator.return_value.fresh = AsyncMock()

        with (
            patch.object(RefreshDatabase, "migrated", False),
            patch("fastapi_startkit.application.app", return_value=application),
            patch("fastapi_startkit.masoniteorm.migrations.Migrator", migrator),
        ):
            await RefreshDatabase.migrate_database()
            await RefreshDatabase.migrate_database()

            assert RefreshDatabase.migrated is True

        application.use_base_path.assert_called_once_with("databases/migrations")
        migrator.assert_called_once_with(migration_directory="/project/databases/migrations")
        migrator.return_value.fresh.assert_awaited_once_with(ignore_fk=True)

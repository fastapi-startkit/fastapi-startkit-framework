from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi_startkit.masoniteorm.testing.transaction import DatabaseTransaction, RefreshDatabase


class TestDatabaseTransaction(IsolatedAsyncioTestCase):
    async def test_asyncStartTestRun_begins_transaction(self):
        tx = DatabaseTransaction()
        mock_db_manager = MagicMock()
        mock_connection = AsyncMock()
        mock_db_manager.connection.return_value = mock_connection

        # Model is imported locally inside asyncStartTestRun, so patch the source module
        with patch("fastapi_startkit.masoniteorm.models.Model") as mock_model_cls:
            mock_model_cls.db_manager = mock_db_manager
            await tx.asyncStartTestRun()

        mock_db_manager.connection.assert_called_once_with(None)
        mock_connection.begin_transaction.assert_awaited_once()
        self.assertIs(tx.connection, mock_connection)

    async def test_asyncStopTestRun_rolls_back_transaction(self):
        tx = DatabaseTransaction()
        mock_connection = AsyncMock()
        tx.connection = mock_connection

        await tx.asyncStopTestRun()

        mock_connection.rollback.assert_awaited_once()

    async def test_start_then_stop_sequence(self):
        tx = DatabaseTransaction()
        mock_db_manager = MagicMock()
        mock_connection = AsyncMock()
        mock_db_manager.connection.return_value = mock_connection

        with patch("fastapi_startkit.masoniteorm.models.Model") as mock_model_cls:
            mock_model_cls.db_manager = mock_db_manager
            await tx.asyncStartTestRun()
            await tx.asyncStopTestRun()

        mock_connection.begin_transaction.assert_awaited_once()
        mock_connection.rollback.assert_awaited_once()


class TestRefreshDatabase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reset the class-level flag before each test
        RefreshDatabase.migrated = False

    async def asyncTearDown(self):
        # Reset again to avoid polluting other test suites
        RefreshDatabase.migrated = False

    async def test_migrate_database_runs_migrator_on_first_call(self):
        mock_migrator = AsyncMock()

        with (
            patch(
                "fastapi_startkit.masoniteorm.migrations.Migrator",
                return_value=mock_migrator,
            ) as MockMigrator,
            patch("fastapi_startkit.application.app") as mock_app_fn,
        ):
            mock_app_fn.return_value.use_base_path.return_value = "/fake/migrations"

            await RefreshDatabase.migrate_database()

        MockMigrator.assert_called_once()
        mock_migrator.fresh.assert_awaited_once_with(ignore_fk=True)
        self.assertTrue(RefreshDatabase.migrated)

    async def test_migrate_database_skips_on_second_call(self):
        mock_migrator = AsyncMock()

        with (
            patch(
                "fastapi_startkit.masoniteorm.migrations.Migrator",
                return_value=mock_migrator,
            ) as MockMigrator,
            patch("fastapi_startkit.application.app") as mock_app_fn,
        ):
            mock_app_fn.return_value.use_base_path.return_value = "/fake/migrations"

            await RefreshDatabase.migrate_database()
            await RefreshDatabase.migrate_database()  # second call — should be a no-op

        # Migrator should only be instantiated once
        MockMigrator.assert_called_once()
        mock_migrator.fresh.assert_awaited_once()

    async def test_asyncStartTestRun_migrates_then_begins_transaction(self):
        db = RefreshDatabase()
        mock_db_manager = MagicMock()
        mock_connection = AsyncMock()
        mock_db_manager.connection.return_value = mock_connection
        mock_migrator = AsyncMock()

        with (
            patch("fastapi_startkit.masoniteorm.models.Model") as mock_model_cls,
            patch(
                "fastapi_startkit.masoniteorm.migrations.Migrator",
                return_value=mock_migrator,
            ),
            patch("fastapi_startkit.application.app") as mock_app_fn,
        ):
            mock_model_cls.db_manager = mock_db_manager
            mock_app_fn.return_value.use_base_path.return_value = "/fake/migrations"
            await db.asyncStartTestRun()

        mock_migrator.fresh.assert_awaited_once_with(ignore_fk=True)
        mock_connection.begin_transaction.assert_awaited_once()
        self.assertTrue(RefreshDatabase.migrated)

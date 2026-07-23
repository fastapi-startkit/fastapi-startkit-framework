import unittest
from unittest.mock import MagicMock

from fastapi_startkit.masoniteorm.query.processors.MSSQLPostProcessor import MSSQLPostProcessor
from fastapi_startkit.masoniteorm.query.processors.MySQLPostProcessor import MySQLPostProcessor
from fastapi_startkit.masoniteorm.query.processors.PostgresPostProcessor import PostgresPostProcessor
from fastapi_startkit.masoniteorm.query.processors.SQLitePostProcessor import SQLitePostProcessor


class TestSQLitePostProcessor(unittest.TestCase):
    """Post processor unit tests — connections are mocked, no live database."""

    def setUp(self):
        self.processor = SQLitePostProcessor()

    def test_process_insert_get_id_fetches_last_row_id(self):
        builder = MagicMock()
        builder.get_connection.return_value.get_last_row_id.return_value = 11

        result = self.processor.process_insert_get_id(builder, {}, "id")

        self.assertEqual(result, {"id": 11})

    def test_process_insert_get_id_keeps_existing_key(self):
        builder = MagicMock()

        result = self.processor.process_insert_get_id(builder, {"id": 5}, "id")

        self.assertEqual(result, {"id": 5})
        builder.get_connection.assert_not_called()

    def test_get_column_value_refetches_from_row(self):
        builder = MagicMock()
        new_builder = builder.select.return_value
        new_builder.first.return_value = {"name": "Joe"}

        result = self.processor.get_column_value(builder, "name", {}, "id", 1)

        self.assertEqual(result, "Joe")
        new_builder.where.assert_called_once_with("id", 1)

    def test_get_column_value_without_id_returns_empty(self):
        builder = MagicMock()

        result = self.processor.get_column_value(builder, "name", {}, None, None)

        self.assertEqual(result, {})


class TestMySQLPostProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = MySQLPostProcessor()

    def test_process_insert_get_id_uses_cursor_lastrowid(self):
        builder = MagicMock()
        builder._connection.get_cursor.return_value.lastrowid = 42

        result = self.processor.process_insert_get_id(builder, {}, "id")

        self.assertEqual(result, {"id": 42})

    def test_process_insert_get_id_keeps_existing_key(self):
        builder = MagicMock()

        result = self.processor.process_insert_get_id(builder, {"id": 7}, "id")

        self.assertEqual(result, {"id": 7})
        builder._connection.get_cursor.assert_not_called()

    def test_get_column_value_refetches_from_row(self):
        builder = MagicMock()
        builder.select.return_value.first.return_value = {"email": "a@b.com"}

        result = self.processor.get_column_value(builder, "email", {}, "id", 3)

        self.assertEqual(result, "a@b.com")

    def test_get_column_value_without_id_returns_empty(self):
        builder = MagicMock()

        result = self.processor.get_column_value(builder, "email", {}, None, None)

        self.assertEqual(result, {})


class TestPostgresPostProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = PostgresPostProcessor()

    def test_process_insert_get_id_maps_lastval_fallback(self):
        result = self.processor.process_insert_get_id(MagicMock(), {"lastval": 9}, "id")

        self.assertEqual(result, {"id": 9})

    def test_process_insert_get_id_passes_through_returning_row(self):
        results = {"id": 3, "name": "Joe"}

        result = self.processor.process_insert_get_id(MagicMock(), results, "id")

        self.assertEqual(result, results)

    def test_get_column_value_reads_present_column(self):
        result = self.processor.get_column_value(MagicMock(), "name", {"name": "Bob"}, "id", 1)

        self.assertEqual(result, "Bob")

    def test_get_column_value_refetches_missing_column(self):
        builder = MagicMock()
        builder.select.return_value.first.return_value = {"name": "Sue"}

        result = self.processor.get_column_value(builder, "name", {}, "id", 2)

        self.assertEqual(result, "Sue")

    def test_get_column_value_without_id_returns_empty(self):
        builder = MagicMock()

        result = self.processor.get_column_value(builder, "name", {}, None, None)

        self.assertEqual(result, {})


class TestMSSQLPostProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = MSSQLPostProcessor()

    def test_process_insert_get_id_casts_numeric_identity(self):
        builder = MagicMock()
        builder.new_connection.return_value.query.return_value = {"id": "9"}

        result = self.processor.process_insert_get_id(builder, {}, "id")

        self.assertEqual(result, {"id": 9})
        self.assertIsInstance(result["id"], int)

    def test_process_insert_get_id_keeps_non_numeric_identity_as_string(self):
        builder = MagicMock()
        builder.new_connection.return_value.query.return_value = {"id": "abc"}

        result = self.processor.process_insert_get_id(builder, {}, "id")

        self.assertEqual(result, {"id": "abc"})

    def test_get_column_value_refetches_from_row(self):
        builder = MagicMock()
        builder.select.return_value.first.return_value = {"name": "Zed"}

        result = self.processor.get_column_value(builder, "name", {}, "id", 4)

        self.assertEqual(result, "Zed")

    def test_get_column_value_without_id_returns_empty(self):
        builder = MagicMock()

        result = self.processor.get_column_value(builder, "name", {}, None, None)

        self.assertEqual(result, {})

import pytest

from fastapi_startkit.masoniteorm.schema import Schema
from fastapi_startkit.masoniteorm.schema.platforms import MySQLPlatform, PostgresPlatform
from fastapi_startkit.masoniteorm.schema.platforms.Platform import Platform
from fastapi_startkit.masoniteorm.schema.Table import Table


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    async def select(self, sql, bindings):
        return self.rows


class TestBasePlatform:
    @pytest.mark.parametrize(
        "method",
        ["columnize_string", "get_table_string", "get_column_string", "get_foreign_key_constraint_string"],
    )
    def test_dialect_hooks_must_be_provided_by_subclasses(self, method):
        with pytest.raises(NotImplementedError):
            getattr(Platform(), method)()

    def test_constraintize_formats_each_constraint(self):
        class UniquePlatform(Platform):
            def get_unique_constraint_string(self):
                return "UNIQUE ({columns})"

        table = Table("users")
        table.add_constraint("users_email_unique", "unique", ["email", "name"])

        assert UniquePlatform().constraintize(table.get_added_constraints(), table) == ["UNIQUE (email, name)"]


class TestCurrentSchemaPythonTypes:
    async def test_mysql_unknown_column_type_falls_back_to_str(self):
        rows = [
            {"Field": "id", "Type": "int", "Default": None},
            {"Field": "shape", "Type": "xml_blob", "Default": None},
        ]

        table = await MySQLPlatform().get_current_schema(FakeConnection(rows), "users")

        known = table.added_columns["id"]
        assert known.column_python_type is Schema._type_hints_map.get(known.column_type, str)
        assert table.added_columns["shape"].column_type is None
        assert table.added_columns["shape"].column_python_type is str

    async def test_postgres_unknown_column_type_falls_back_to_str(self):
        rows = [
            {"column_name": "id", "data_type": "integer", "column_default": None},
            {"column_name": "shape", "data_type": "xml_blob", "column_default": None},
        ]

        table = await PostgresPlatform().get_current_schema(FakeConnection(rows), "users")

        assert table.added_columns["id"].column_python_type is int
        assert table.added_columns["shape"].column_type is None
        assert table.added_columns["shape"].column_python_type is str

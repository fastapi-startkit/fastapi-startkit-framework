from contextlib import asynccontextmanager

import pytest

from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint
from fastapi_startkit.masoniteorm.schema.platforms.MSSQLPlatform import MSSQLPlatform
from fastapi_startkit.masoniteorm.schema.platforms.SQLitePlatform import SQLitePlatform
from fastapi_startkit.masoniteorm.schema.Table import Table
from fastapi_startkit.masoniteorm.schema.TableDiff import TableDiff


def create_blueprint():
    return Blueprint(grammar=None, table=Table("users"), platform=SQLitePlatform, dry=True)


def alter_blueprint():
    return Blueprint(grammar=None, table=TableDiff("users"), platform=SQLitePlatform, dry=True)


class TestColumnModifiers:
    def test_modifiers_apply_to_last_column(self):
        blueprint = create_blueprint()
        blueprint.string("name").default("guest").comment("display name").after("id").unique().nullable()

        column = blueprint.table.added_columns["name"]
        assert column.default == "guest"
        assert column.comment == "display name"
        assert column.get_after_column() == "id"
        assert column.is_null is True
        assert "users_name_unique" in blueprint.table.added_constraints

    def test_index_modifiers_use_last_column_name(self):
        blueprint = create_blueprint()
        blueprint.text("bio").fulltext().index().primary()
        blueprint.integer("age").unsigned()

        assert "bio_fulltext" in blueprint.table.added_constraints
        assert "users_bio_index" in blueprint.table.added_indexes
        assert "users_bio_primary" in blueprint.table.added_constraints
        assert blueprint.table.added_columns["age"]._signed == "unsigned"

    def test_modifier_without_column_raises(self):
        with pytest.raises(AttributeError, match="single column"):
            create_blueprint().default("x")

    def test_modifier_after_morphs_raises(self):
        with pytest.raises(AttributeError, match="single column"):
            create_blueprint().morphs("record").comment("x")

    def test_nullable_after_morphs_is_noop(self):
        blueprint = create_blueprint().morphs("record").nullable()

        assert blueprint.table.added_columns["record_id"].is_null is False
        assert blueprint.table.added_columns["record_type"].is_null is False


class TestAlterOnlyMethods:
    def test_alter_methods_record_on_table_diff(self):
        blueprint = alter_blueprint()
        blueprint.string("email").change()
        blueprint.drop_column("age")
        blueprint.drop_index(["age"])
        blueprint.drop_index("users_name_index")
        blueprint.drop_unique(["email"])
        blueprint.drop_unique("users_code_unique")
        blueprint.drop_primary(["id"])
        blueprint.drop_primary("users_uuid_primary")
        blueprint.drop_foreign(["team_id"])
        blueprint.drop_foreign("users_org_id_foreign")

        table = blueprint.table
        assert isinstance(table, TableDiff)
        assert "email" in table.changed_columns
        assert table.dropped_columns == ["age"]
        assert table.removed_indexes == ["users_age_index", "users_name_index"]
        assert table.removed_unique_indexes == ["users_email_unique", "users_code_unique"]
        assert table.dropped_primary_keys == ["users_id_primary", "users_uuid_primary"]
        assert table.dropped_foreign_keys == ["users_team_id_foreign", "users_org_id_foreign"]

    def test_alter_method_on_create_table_raises(self):
        with pytest.raises(AttributeError, match="Schema.table"):
            create_blueprint().drop_column("age")


class FakeConnection:
    def __init__(self):
        self.statements = []

    @classmethod
    def get_default_platform(cls):
        return MSSQLPlatform

    @asynccontextmanager
    async def transaction(self):
        yield

    async def statement(self, query, bindings=None):
        self.statements.append(query)
        return True


class TestExecution:
    def test_platform_defaults_to_connection_platform(self):
        blueprint = Blueprint(grammar=None, table=Table("users"), connection=FakeConnection())

        assert blueprint.platform is MSSQLPlatform

    def test_missing_platform_and_connection_raises(self):
        with pytest.raises(AttributeError, match="no connection"):
            Blueprint(grammar=None, table=Table("users"))

    def test_sync_exit_requires_async_with(self):
        blueprint = Blueprint(grammar=None, table=Table("users"), platform=SQLitePlatform)

        with pytest.raises(TypeError, match="async with"):
            with blueprint:
                pass

    async def test_async_exit_without_connection_raises(self):
        blueprint = Blueprint(grammar=None, table=Table("users"), platform=SQLitePlatform, action="create")

        with pytest.raises(AttributeError, match="no connection"):
            async with blueprint:
                blueprint.string("name")

    async def test_mssql_alter_resolves_current_schema(self):
        connection = FakeConnection()
        blueprint = Blueprint(grammar=None, table=TableDiff("users"), connection=connection, action="alter")

        async with blueprint:
            blueprint.string("name")

        assert isinstance(blueprint.table, TableDiff)
        assert isinstance(blueprint.table.from_table, Table)
        assert connection.statements == ["ALTER TABLE [users] ADD [name] VARCHAR(255) NOT NULL"]

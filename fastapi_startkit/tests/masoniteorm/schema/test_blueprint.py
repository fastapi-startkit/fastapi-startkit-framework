import pytest

from fastapi_startkit.masoniteorm.schema.Blueprint import Blueprint
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

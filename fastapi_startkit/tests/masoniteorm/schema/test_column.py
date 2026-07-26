"""Unit tests for the schema Column builder (task #1214)."""

from fastapi_startkit.masoniteorm.schema.Column import Column


def make_column(**kwargs):
    defaults = {"name": "email", "column_type": "string"}
    defaults.update(kwargs)
    return Column(**defaults)


class TestColumnDefaults:
    def test_initial_state(self):
        col = make_column(length=255)
        assert col.name == "email"
        assert col.column_type == "string"
        assert col.length == 255
        assert col.values == []
        assert col.is_null is False
        assert col.primary is False
        assert col.comment is None

    def test_values_defaults_to_empty_list(self):
        assert make_column(values=None).values == []
        assert make_column(values=["a", "b"]).values == ["a", "b"]


class TestNullability:
    def test_nullable_sets_flag_and_returns_self(self):
        col = make_column()
        assert col.nullable() is col
        assert col.is_null is True

    def test_not_nullable_clears_flag(self):
        col = make_column(nullable=True)
        assert col.not_nullable() is col
        assert col.is_null is False


class TestSignedness:
    def test_signed(self):
        col = make_column()
        assert col.signed() is col
        assert col._signed == "signed"

    def test_unsigned(self):
        col = make_column()
        assert col.unsigned() is col
        assert col._signed == "unsigned"


class TestPrimaryAndComment:
    def test_set_as_primary(self):
        col = make_column()
        col.set_as_primary()
        assert col.primary is True

    def test_add_comment_returns_self(self):
        col = make_column()
        assert col.add_comment("the user email") is col
        assert col.comment == "the user email"


class TestRenameAndPositioning:
    def test_rename_records_old_column(self):
        col = make_column()
        assert col.rename("old_email") is col
        assert col.old_column == "old_email"

    def test_after_sets_and_get_after_column_reads(self):
        col = make_column()
        assert col.after("created_at") is col
        assert col.get_after_column() == "created_at"

    def test_get_after_column_defaults_to_none(self):
        assert make_column().get_after_column() is None


class TestChangeAndCurrent:
    def test_change_marks_modify_action(self):
        col = make_column()
        assert col.change() is col
        assert col._action == "modify"

    def test_use_current_sets_default_current(self):
        col = make_column()
        assert col.use_current() is col
        assert col.default == "current"


class TestDefaultValue:
    def test_default_value_is_stored_as_attribute_from_constructor(self):
        col = make_column(default="anon", default_is_raw=True)
        assert col.default == "anon"
        assert col.default_is_raw is True

    def test_default_method_is_reachable_on_the_class(self):
        # The constructor assigns ``self.default`` as an attribute, shadowing the
        # method on instances; the method is still invocable via the class.
        col = make_column()
        assert Column.default(col, "seed", raw=True) is col
        assert col.default == "seed"
        assert col.default_is_raw is True

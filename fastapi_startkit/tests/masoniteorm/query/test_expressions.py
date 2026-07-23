"""Unit tests for ORM query expression helper classes (task #1214).

These classes carry the parsing/normalisation logic the grammars rely on
(alias splitting, direction inference, ON-clause construction), so the tests
assert on that behaviour rather than merely instantiating the objects.
"""

import warnings

import pytest

from fastapi_startkit.masoniteorm.expressions.expressions import (
    AggregateExpression,
    BetweenExpression,
    GroupByExpression,
    HavingExpression,
    JoinClause,
    OnClause,
    OnValueClause,
    OrderByExpression,
    QueryExpression,
    Raw,
    SelectExpression,
    SubGroupExpression,
    SubSelectExpression,
    UpdateQueryExpression,
)


class TestQueryExpression:
    def test_stores_all_attributes(self):
        expr = QueryExpression("age", ">", 18, value_type="value", keyword="where")
        assert expr.column == "age"
        assert expr.equality == ">"
        assert expr.value == 18
        assert expr.value_type == "value"
        assert expr.keyword == "where"
        assert expr.raw is False
        assert expr.bindings == ()


class TestHavingExpression:
    def test_infers_equality_when_only_value_given(self):
        expr = HavingExpression("total", 100)
        assert expr.equality == "="
        assert expr.value == 100
        assert expr.value_type == "having"

    def test_keeps_explicit_equality_and_value(self):
        expr = HavingExpression("total", ">=", 100)
        assert expr.equality == ">="
        assert expr.value == 100


class TestBetweenExpression:
    def test_defaults(self):
        expr = BetweenExpression("age", 18, 30)
        assert expr.low == 18
        assert expr.high == 30
        assert expr.equality == "BETWEEN"
        assert expr.value_type == "BETWEEN"
        assert expr.value is None
        assert expr.raw is False


class TestSelectExpression:
    def test_splits_column_and_alias(self):
        expr = SelectExpression("name as full_name")
        assert expr.column == "name"
        assert expr.alias == "full_name"

    def test_strips_surrounding_whitespace(self):
        expr = SelectExpression("   email   ")
        assert expr.column == "email"
        assert expr.alias is None

    def test_raw_column_is_not_split(self):
        expr = SelectExpression("count(*) as total", raw=True)
        assert expr.column == "count(*) as total"
        assert expr.alias is None


class TestOrderByExpression:
    def test_defaults_to_ascending(self):
        expr = OrderByExpression("name")
        assert expr.column == "name"
        assert expr.direction == "ASC"

    def test_infers_descending_from_suffix(self):
        expr = OrderByExpression("created_at desc")
        assert expr.column == "created_at"
        assert expr.direction == "DESC"

    def test_infers_ascending_from_suffix(self):
        expr = OrderByExpression("name asc")
        assert expr.column == "name"
        assert expr.direction == "ASC"

    def test_raw_disables_suffix_parsing(self):
        expr = OrderByExpression("name desc", raw=True)
        assert expr.column == "name desc"
        assert expr.direction == "ASC"


class TestGroupByExpression:
    def test_strips_column(self):
        expr = GroupByExpression("  category  ")
        assert expr.column == "category"
        assert expr.raw is False


class TestAggregateExpression:
    def test_plain_column(self):
        expr = AggregateExpression(aggregate="SUM", column="amount")
        assert expr.aggregate == "SUM"
        assert expr.column == "amount"
        assert expr.alias is False

    def test_splits_alias(self):
        expr = AggregateExpression(aggregate="SUM", column="amount as total")
        assert expr.column == "amount"
        assert expr.alias == "total"


class TestRaw:
    def test_stores_expression(self):
        assert Raw("NOW()").expression == "NOW()"


class TestUpdateQueryExpression:
    def test_defaults(self):
        expr = UpdateQueryExpression("name", "bob")
        assert expr.column == "name"
        assert expr.value == "bob"
        assert expr.update_type == "keyvalue"


class TestSubExpressions:
    def test_sub_select_holds_builder(self):
        sentinel = object()
        assert SubSelectExpression(sentinel).builder is sentinel

    def test_sub_group_default_alias(self):
        sentinel = object()
        expr = SubGroupExpression(sentinel)
        assert expr.builder is sentinel
        assert expr.alias == "group"


class TestJoinClause:
    def test_parses_table_alias(self):
        clause = JoinClause("users as u")
        assert clause.table == "users"
        assert clause.alias == "u"
        assert clause.clause == "join"

    def test_no_alias(self):
        clause = JoinClause("users", clause="left")
        assert clause.table == "users"
        assert clause.alias is None
        assert clause.clause == "left"

    def test_on_builds_and_clause(self):
        clause = JoinClause("users").on("users.id", "=", "posts.user_id")
        [on] = clause.get_on_clauses()
        assert isinstance(on, OnClause)
        assert on.column1 == "users.id"
        assert on.column2 == "posts.user_id"
        assert on.operator == "and"

    def test_or_on_builds_or_clause(self):
        clause = JoinClause("users").or_on("a", "=", "b")
        assert clause.get_on_clauses()[0].operator == "or"

    def test_chaining_returns_self(self):
        clause = JoinClause("users")
        assert clause.on("a", "=", "b") is clause

    def test_on_value_with_operator_and_value(self):
        clause = JoinClause("users").on_value("age", ">", 18)
        on = clause.get_on_clauses()[0]
        assert isinstance(on, OnValueClause)
        assert on.equality == ">"
        assert on.value == 18
        assert on.operator == "and"

    def test_on_value_with_single_value_defaults_operator(self):
        clause = JoinClause("users").on_value("active", 1)
        on = clause.get_on_clauses()[0]
        assert on.equality == "="
        assert on.value == 1

    def test_or_on_value_sets_or_operator(self):
        clause = JoinClause("users").or_on_value("age", ">", 18)
        assert clause.get_on_clauses()[0].operator == "or"

    def test_on_null(self):
        clause = JoinClause("users").on_null("deleted_at")
        on = clause.get_on_clauses()[0]
        assert on.value_type == "NULL"
        assert on.value is None

    def test_on_not_null(self):
        clause = JoinClause("users").on_not_null("verified_at")
        on = clause.get_on_clauses()[0]
        assert on.value_type == "NOT NULL"
        assert on.value is True

    def test_or_on_null(self):
        clause = JoinClause("users").or_on_null("deleted_at")
        assert clause.get_on_clauses()[0].operator == "or"

    def test_or_on_not_null(self):
        clause = JoinClause("users").or_on_not_null("verified_at")
        on = clause.get_on_clauses()[0]
        assert on.operator == "or"
        assert on.value_type == "NOT NULL"

    def test_invalid_operator_raises(self):
        with pytest.raises(ValueError):
            JoinClause("users").on_value("age", "bogus", 18)

    def test_where_is_deprecated_alias_of_on_value(self):
        clause = JoinClause("users")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = clause.where("age", ">", 18)
        assert result is clause
        assert clause.get_on_clauses()[0].equality == ">"

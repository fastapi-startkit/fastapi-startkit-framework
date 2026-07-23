"""Unit tests for the fluent JSON assertion API (AssertableJson / TestResponse)."""

import pytest

from fastapi_startkit.fastapi.testing.assertable_json import (
    AssertableJson,
    assert_json_structure,
)


def aj(data):
    return AssertableJson(data)


# --------------------------------------------------------------------------- #
# where / where_not / where_all
# --------------------------------------------------------------------------- #
def test_where_happy_path():
    aj({"id": 1, "name": "Bedu"}).where("id", 1).where("name", "Bedu").etc()


def test_where_mismatch_raises_with_full_path():
    with pytest.raises(AssertionError) as exc:
        aj({"id": 1}).where("id", 2)
    assert "[id]" in str(exc.value)


def test_where_missing_property_raises():
    with pytest.raises(AssertionError) as exc:
        aj({"id": 1}).where("missing", 1)
    assert "[missing] does not exist" in str(exc.value)


def test_where_predicate_matcher():
    aj({"age": 30}).where("age", lambda v: v > 18).etc()


def test_where_predicate_matcher_failure():
    with pytest.raises(AssertionError):
        aj({"age": 10}).where("age", lambda v: v > 18)


def test_where_dotted_key():
    data = {"user": {"profile": {"email": "a@b.com"}}}
    aj(data).where("user.profile.email", "a@b.com").etc()


def test_where_not():
    aj({"role": "user"}).where_not("role", "admin").etc()
    with pytest.raises(AssertionError):
        aj({"role": "admin"}).where_not("role", "admin")


def test_where_all():
    aj({"a": 1, "b": 2}).where_all({"a": 1, "b": 2}).etc()


# --------------------------------------------------------------------------- #
# where_type
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,type_name",
    [
        ("x", "string"),
        (5, "integer"),
        (1.5, "double"),
        (True, "boolean"),
        ([], "array"),
        ({}, "object"),
        (None, "null"),
    ],
)
def test_where_type_matches(value, type_name):
    aj({"v": value}).where_type("v", type_name).etc()


def test_where_type_bool_is_not_integer():
    with pytest.raises(AssertionError):
        aj({"v": True}).where_type("v", "integer")


def test_where_type_union():
    aj({"v": None}).where_type("v", "string|null").etc()
    aj({"v": "x"}).where_type("v", ["string", "null"]).etc()


# --------------------------------------------------------------------------- #
# has / has_all / has_any / missing / count
# --------------------------------------------------------------------------- #
def test_has_presence():
    aj({"id": 1}).has("id").etc()


def test_has_length():
    aj({"items": [1, 2, 3]}).has("items", 3).etc()


def test_has_length_mismatch():
    with pytest.raises(AssertionError):
        aj({"items": [1, 2]}).has("items", 3)


def test_has_nested_scope():
    data = {"profile": {"email": "a@b.com", "name": "Bedu"}}
    aj(data).has(
        "profile",
        lambda p: p.where("email", "a@b.com").where("name", "Bedu"),
    ).etc()


def test_has_length_and_scope():
    data = {"rows": [{"id": 1}, {"id": 2}]}
    aj(data).has("rows", 2, lambda r: r.first(lambda f: f.where("id", 1).etc())).etc()


def test_has_all_and_has_any():
    aj({"a": 1, "b": 2}).has_all("a", "b").etc()
    aj({"a": 1, "b": 2}).has_all(["a", "b"]).etc()
    aj({"a": 1}).has_any("a", "z").etc()


def test_has_any_failure():
    with pytest.raises(AssertionError):
        aj({"a": 1}).has_any("x", "y")


def test_missing_and_missing_all():
    aj({"a": 1}).missing("b").has("a").etc()
    aj({"a": 1}).missing_all("b", "c").has("a").etc()
    with pytest.raises(AssertionError):
        aj({"a": 1}).missing("a")


def test_count():
    aj({"items": [1, 2]}).count("items", 2).etc()


# --------------------------------------------------------------------------- #
# first / each
# --------------------------------------------------------------------------- #
def test_first_on_list():
    data = {"users": [{"id": 1}, {"id": 2}]}
    aj(data).has("users", lambda u: u.first(lambda f: f.where("id", 1).etc())).etc()


def test_each_on_list():
    data = [{"id": 1}, {"id": 2}]
    aj(data).each(lambda item: item.has("id"))


def test_each_empty_list_ok():
    aj([]).each(lambda item: item.where("id", 1))


# --------------------------------------------------------------------------- #
# etc() and strict interaction verification (_verify)
# --------------------------------------------------------------------------- #
def test_unasserted_prop_fails():
    with pytest.raises(AssertionError) as exc:
        fluent = aj({"id": 1, "secret": "leak"}).where("id", 1)
        fluent._verify()
    assert "secret" in str(exc.value)


def test_etc_acknowledges_remaining():
    fluent = aj({"id": 1, "secret": "leak"}).where("id", 1).etc()
    fluent._verify()  # should not raise


def test_verify_nested_scope_enforced():
    data = {"profile": {"email": "a@b.com", "name": "Bedu"}}
    with pytest.raises(AssertionError) as exc:
        aj(data).has("profile", lambda p: p.where("email", "a@b.com")).etc()
    assert "name" in str(exc.value)


# --------------------------------------------------------------------------- #
# where_all_type
# --------------------------------------------------------------------------- #
def test_where_all_type():
    data = {"name": "Phoenix Suns", "sport": "basketball"}
    aj(data).where_all_type({"name": "string", "sport": "string"}).etc()


def test_where_all_type_failure():
    with pytest.raises(AssertionError):
        aj({"name": "x", "rank": 1}).where_all_type({"name": "string", "rank": "string"})


# --------------------------------------------------------------------------- #
# Dotted keys that index into lists (e.g. "teams.0")
# --------------------------------------------------------------------------- #
def test_has_dotted_list_index_scope():
    data = {"teams": [{"name": "Phoenix Suns", "sport": "basketball"}]}
    aj(data).has("teams", 1).has(
        "teams.0",
        lambda team: team.where("name", "Phoenix Suns").etc(),
    ).etc()


def test_where_dotted_list_index():
    data = {"teams": [{"name": "Phoenix Suns"}]}
    aj(data).where("teams.0.name", "Phoenix Suns").etc()


# --------------------------------------------------------------------------- #
# assert_json_structure
# --------------------------------------------------------------------------- #
def test_structure_simple_list():
    assert_json_structure(["name", "sport"], {"name": "x", "sport": "y"})


def test_structure_missing_key_fails():
    with pytest.raises(AssertionError) as exc:
        assert_json_structure(["name", "sport"], {"name": "x"})
    assert "sport" in str(exc.value)


def test_structure_wildcard_over_list():
    data = {"teams": [{"name": "a", "sport": "b"}, {"name": "c", "sport": "d"}]}
    assert_json_structure({"teams": {"*": ["name", "sport"]}}, data)


def test_structure_wildcard_failure():
    data = {"teams": [{"name": "a", "sport": "b"}, {"name": "c"}]}
    with pytest.raises(AssertionError) as exc:
        assert_json_structure({"teams": {"*": ["name", "sport"]}}, data)
    assert "teams.1" in str(exc.value)


def test_structure_nested_dict():
    data = {"user": {"profile": {"email": "a@b.com"}}}
    assert_json_structure({"user": {"profile": ["email"]}}, data)


def test_structure_leaf_none_presence():
    assert_json_structure({"meta": None, "data": ["id"]}, {"meta": 1, "data": {"id": 5}})


# --------------------------------------------------------------------------- #
# Remaining phase-2 stubs
# --------------------------------------------------------------------------- #
def test_phase2_stubs_raise_not_implemented():
    for call in (
        lambda: aj({"a": [1]}).where_contains("a", 1),
        lambda: aj({"a": [1]}).count_between("a", 1, 2),
    ):
        with pytest.raises(NotImplementedError):
            call()

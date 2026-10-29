import re
from decimal import Decimal
from typing import Any

import pytest

from fastapi_startkit.validation import AsyncRule, Rule
from fastapi_startkit.validation.rules import (
    Between,
    Boolean,
    Confirmed,
    EmailRule,
    In,
    Integer,
    Max,
    Min,
    NotIn,
    Nullable,
    Numeric,
    Regex,
    Required,
    RequiredIf,
    SameAs,
    String,
    Url,
    humanize,
    is_empty,
)


@pytest.mark.parametrize("value", [None, "", "   ", [], (), set(), {}])
def test_empty_values(value):
    assert is_empty(value)


@pytest.mark.parametrize("value", [0, False, "a", [0], {"a": 1}])
def test_non_empty_values(value):
    assert not is_empty(value)


def test_humanize():
    assert humanize("password_confirmation") == "password confirmation"
    assert humanize("address.street_name") == "address street name"


@pytest.mark.parametrize(
    ("rule", "passing", "failing"),
    [
        (Required(), ["a", 0, [1]], [None, "", " ", []]),
        (Nullable(), [None, "a"], []),
        (String(), ["a", ""], [1, None, b"a"]),
        (Integer(), [1, -2, "3", " -4 "], [True, 1.5, "1.5", "a", None]),
        (Numeric(), [1, 1.5, Decimal("2"), "3.25", "-1"], [True, "abc", None, [1]]),
        (Boolean(), [True, False, 0, 1, "0", "1"], ["true", 2, None]),
        (Min(3), ["abc", 3, 4.5, [1, 2, 3], Decimal("3")], ["ab", 2, [1], True, object()]),
        (Max(3), ["abc", 3, [1, 2]], ["abcd", 4, [1, 2, 3, 4]]),
        (Between(2, 4), ["ab", 3, [1, 2, 3, 4]], ["a", 5, [1]]),
        (EmailRule(), ["a@b.co", "first.last@sub.example.org"], ["a@b", "a b@c.de", "plain", 5]),
        (Url(), ["https://example.com/path", "ftp://files.example.com"], ["example.com", "http://", 5]),
        (Regex(r"^\d{3}$"), ["123"], ["12", "abcd", 123]),
        (Regex(re.compile("ab")), ["xaby"], ["ba"]),
        (In(["a", "b"]), ["a", "b"], ["c", None]),
        (In({"a", "b"}), ["a"], [["a"], {"a": 1}]),
        (NotIn({"a", "b"}), ["c", ["a"], {"a": 1}], ["a"]),
        (NotIn(["a", "b"]), ["c"], ["a"]),
    ],
)
def test_rule_passes_and_fails(rule: Rule, passing: list[Any], failing: list[Any]):
    for value in passing:
        assert rule.passes("field", value, {}), value
    for value in failing:
        assert not rule.passes("field", value, {}), value


def test_required_if_only_applies_when_other_matches():
    rule = RequiredIf("is_business", True)

    assert rule.passes("tax_id", None, {"is_business": False})
    assert rule.passes("tax_id", "123", {"is_business": True})
    assert not rule.passes("tax_id", None, {"is_business": True})
    assert rule.format_message("tax_id", None, {}) == "The tax id field is required when is business is true."


def test_same_as_compares_with_other_field():
    rule = SameAs("password")

    assert rule.passes("password_confirmation", "secret", {"password": "secret"})
    assert not rule.passes("password_confirmation", "other", {"password": "secret"})
    assert rule.format_message("password_confirmation", "x", {}) == (
        "The password confirmation field must match password."
    )


def test_confirmed_compares_with_confirmation_field():
    rule = Confirmed()

    assert rule.passes("password", "secret", {"password_confirmation": "secret"})
    assert not rule.passes("password", "secret", {})
    assert rule.format_message("password", "secret", {}) == "The password field confirmation does not match."


@pytest.mark.parametrize(
    ("rule", "value", "message"),
    [
        (Min(3), "ab", "The name field must be at least 3 characters."),
        (Min(3), 2, "The name field must be at least 3."),
        (Min(3), [1], "The name field must have at least 3 items."),
        (Max(3), "abcd", "The name field must not be greater than 3 characters."),
        (Max(3), 4, "The name field must not be greater than 3."),
        (Max(3), [1, 2, 3, 4], "The name field must not have more than 3 items."),
        (Between(2, 4), "a", "The name field must be between 2 and 4 characters."),
        (Between(2, 4), 5, "The name field must be between 2 and 4."),
        (Between(2, 4), [1], "The name field must have between 2 and 4 items."),
        (Required(), None, "The name field is required."),
        (String(), 1, "The name field must be a string."),
        (Integer(), "a", "The name field must be an integer."),
        (Numeric(), "a", "The name field must be a number."),
        (Boolean(), "a", "The name field must be true or false."),
        (EmailRule(), "a", "The name field must be a valid email address."),
        (Url(), "a", "The name field must be a valid URL."),
        (Regex("x"), "a", "The name field format is invalid."),
        (In(["x"]), "a", "The selected name is invalid."),
    ],
)
def test_default_messages(rule: Rule, value: Any, message: str):
    assert rule.format_message("name", value, {}) == message


def test_custom_string_message_replaces_placeholders():
    rule = Between(2, 4, ":attribute needs :min-:max (:minimum stays)")

    assert rule.format_message("user_name", "a", {}) == "user name needs 2-4 (:minimum stays)"


def test_custom_callable_message_receives_field_value_and_data():
    rule = Required(lambda field, value, data: f"{field}={value!r} with {sorted(data)}")

    assert rule.format_message("username", "", {"a": 1}) == "username='' with ['a']"


def test_base_rules_pass_by_default():
    assert Rule().passes("field", "value", {})
    assert Rule().format_message("field", "value", {}) == "The field field is invalid."


async def test_base_async_rule_passes_by_default():
    assert await AsyncRule().passes("field", "value", {})


def test_required_if_renders_booleans_in_lowercase():
    assert RequiredIf("active", False).format_message("reason", None, {}) == (
        "The reason field is required when active is false."
    )
    assert (
        RequiredIf("kind", "pro").format_message("tax_id", None, {}) == "The tax id field is required when kind is pro."
    )


def test_size_rules_compare_numeric_value_when_numeric():
    rule = Max(10)
    rule.numeric = True

    assert rule.passes("amount", "9.5", {})
    assert not rule.passes("amount", "25", {})
    assert not rule.passes("amount", "abc", {})
    assert rule.format_message("amount", "25", {}) == "The amount field must not be greater than 10."

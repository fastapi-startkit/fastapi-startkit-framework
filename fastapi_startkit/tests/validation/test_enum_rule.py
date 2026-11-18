import tempfile
from enum import Enum, IntEnum, StrEnum
from pathlib import Path
from typing import Annotated

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.validation import EnumRule, Field, FormRequest, Validated


class Status(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Priority(IntEnum):
    LOW = 1
    HIGH = 2


class Color(Enum):
    RED = "red"
    ONE = 1


class Other(StrEnum):
    DRAFT = "draft"


def passes(rule, value, data=None):
    return rule.passes("status", value, data or {})


@pytest.mark.parametrize("value", ["draft", Status.PUBLISHED, "archived"])
def test_str_enum_accepts_backing_values_and_members(value):
    assert passes(EnumRule(Status), value)


@pytest.mark.parametrize("value", [1, 2, Priority.HIGH])
def test_int_enum_accepts_backing_values_and_members(value):
    assert passes(EnumRule(Priority), value)


@pytest.mark.parametrize("value", ["red", 1, Color.RED])
def test_plain_enum_accepts_backing_values_and_members(value):
    assert passes(EnumRule(Color), value)


@pytest.mark.parametrize(
    ("enum", "value"),
    [
        (Status, "deleted"),
        (Status, "DRAFT"),
        (Status, 1),
        (Status, Other.DRAFT),
        (Priority, "1"),
        (Priority, 1.0),
        (Priority, True),
        (Priority, 3),
        (Color, True),
        (Color, ["red"]),
    ],
)
def test_rejects_unknown_or_mistyped_values(enum, value):
    assert not passes(EnumRule(enum), value)


def test_only_restricts_cases():
    rule = EnumRule(Status).only([Status.DRAFT, "published"])

    assert passes(rule, "draft")
    assert passes(rule, Status.PUBLISHED)
    assert not passes(rule, "archived")


def test_only_accepts_a_single_case_and_replaces_previous_cases():
    rule = EnumRule(Status).only([Status.DRAFT]).only("archived")

    assert passes(rule, "archived")
    assert not passes(rule, "draft")


def test_except_excludes_cases():
    rule = EnumRule(Priority).except_(Priority.LOW)

    assert passes(rule, 2)
    assert not passes(rule, 1)


def test_only_and_except_intersect():
    rule = EnumRule(Status, only=[Status.DRAFT, Status.PUBLISHED], except_=[Status.PUBLISHED])

    assert passes(rule, "draft")
    assert not passes(rule, "published")
    assert not passes(rule, "archived")


@pytest.mark.parametrize(
    ("enum", "case"), [(Status, "deleted"), (Priority, True), (Priority, "1"), (Status, Other.DRAFT)]
)
def test_unknown_or_mistyped_restriction_case_raises(enum, case):
    with pytest.raises(ValueError):
        EnumRule(enum).only([case])


def test_when_applies_callback_for_true_condition():
    rule = EnumRule(Status).when(True, lambda rule: rule.only(Status.DRAFT))

    assert passes(rule, "draft")
    assert not passes(rule, "published")


def test_when_evaluates_callable_conditions_against_data_without_leaking():
    rule = EnumRule(Status).when(
        lambda data: data.get("role") != "editor",
        lambda rule: rule.only(Status.DRAFT),
        lambda rule: rule.except_(Status.ARCHIVED),
    )

    assert not passes(rule, "published", {"role": "guest"})
    assert passes(rule, "published", {"role": "editor"})
    assert not passes(rule, "archived", {"role": "editor"})
    assert passes(rule, "draft", {"role": "guest"})
    assert rule.allowed is None
    assert rule.excluded == []


def test_when_without_default_keeps_rule_for_false_condition():
    rule = EnumRule(Status).when(False, lambda rule: rule.only(Status.DRAFT))

    assert passes(rule, "archived")


def test_default_message_and_values_placeholder():
    rule = EnumRule(Status, except_=[Status.ARCHIVED])

    assert rule.format_message("status", "x", {}) == "The selected status is invalid."
    rule.custom_message = "The :attribute must be one of: :values."
    assert rule.format_message("status", "x", {}) == "The status must be one of: draft, published."


def test_values_placeholder_follows_when_restrictions():
    rule = EnumRule(Status, message="Pick :values.").when(
        lambda data: data.get("role") == "guest", lambda rule: rule.only(Status.DRAFT)
    )

    assert rule.format_message("status", "published", {"role": "guest"}) == "Pick draft."
    assert rule.format_message("status", "x", {"role": "editor"}) == "Pick draft, published, archived."


async def test_field_enum_checks_values_and_skips_empty_values():
    field = Field().enum(Status, only=[Status.DRAFT], msg="Bad :attribute.")

    assert await field.check("status", "draft", {}) is None
    assert await field.check("status", "published", {}) == "Bad status."
    assert await field.check("status", None, {}) is None
    assert await Field().required().enum(Status).check("status", None, {}) == "The status field is required."


class Article(FormRequest):
    role: str = "guest"
    status: Annotated[
        str,
        Field()
        .required()
        .add(
            EnumRule(Status, except_=[Status.ARCHIVED]).when(
                lambda data: data["role"] != "editor", lambda rule: rule.only(Status.DRAFT)
            )
        ),
    ]
    priority: Annotated[int | None, Field().nullable().enum(Priority)] = None


class EnumValidationTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            app = Application(base_path=Path(self._tmp_dir.name), providers=[FastAPIProvider])

            @app.fastapi.post("/articles")
            async def store(data: Validated[Article]):
                return data.model_dump()

            @app.fastapi.get("/articles")
            async def index(query: Validated[Article]):
                return query.model_dump()

            self._application = app
        return self._application

    async def test_valid_enum_values_reach_the_endpoint(self):
        response = await self.post("/articles", json={"role": "editor", "status": "published", "priority": 2})

        response.assert_status(200)
        self.assertEqual(response.json(), {"role": "editor", "status": "published", "priority": 2})

    async def test_query_string_values_are_checked_after_coercion(self):
        response = await self.get("/articles?status=draft&priority=1", headers={"accept": "application/json"})

        response.assert_status(200)
        self.assertEqual(response.json()["priority"], 1)

    async def test_invalid_and_restricted_values_are_rejected(self):
        response = await self.post("/articles", json={"status": "published", "priority": 5})

        response.assert_status(422)
        self.assertEqual(
            response.json()["errors"],
            {"status": ["The selected status is invalid."], "priority": ["The selected priority is invalid."]},
        )

    async def test_excluded_case_is_rejected_for_editors(self):
        response = await self.post("/articles", json={"role": "editor", "status": "archived"})

        response.assert_status(422)
        self.assertEqual(response.json()["errors"], {"status": ["The selected status is invalid."]})

from collections.abc import Mapping
from typing import Annotated, Any

import asyncio

import pytest
from pydantic import BaseModel, ValidationError

from fastapi_startkit.exceptions import AuthorizationException, HttpException
from fastapi_startkit.validation import (
    AsyncRule,
    Email,
    Field,
    FormRequest,
    Rule,
    ValidationException,
    Validator,
)


class Captcha(Rule):
    message = "The :attribute is wrong."

    def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value == "42"


class NotReserved(AsyncRule):
    message = "The :attribute :value is reserved."

    def __init__(self, reserved: str) -> None:
        super().__init__()
        self.reserved = reserved

    def replacements(self) -> Mapping[str, Any]:
        return {"value": self.reserved}

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        return value != self.reserved


class RegisterUser(FormRequest):
    password_confirmation: Annotated[str, Field().required().same_as("password")]
    email: Annotated[str, Email().required()]
    username: Annotated[
        str,
        Field()
        .required(msg=lambda field, value, data: f"{field} is required but you provided {value!r}")
        .string()
        .min(3)
        .max(10)
        .add(NotReserved("admin")),
    ]
    password: Annotated[str, Field().required().password()]
    age: Annotated[int | None, Field().min(18).msg("Adults only.")] = None
    nickname: Annotated[str | None, Field().nullable().min(3)] = None
    captcha: Annotated[str | None, Field().add(Captcha())] = None
    tax_id: Annotated[str | None, Field().required_if("is_business", True)] = None
    is_business: bool = False


VALID = {
    "email": "jane@example.com",
    "username": "jane",
    "password": "secret123",
    "password_confirmation": "secret123",
}


async def errors_of(data: Any, model: type[FormRequest] = RegisterUser, context=None) -> dict[str, list[str]]:
    with pytest.raises(ValidationException) as caught:
        await model.validate_input(data, context)
    return caught.value.errors


async def test_valid_data_builds_the_model():
    user = await RegisterUser.validate_input({**VALID, "age": "20", "nickname": None})

    assert user.age == 20
    assert user.nickname is None
    assert user.tax_id is None


async def test_missing_required_fields_use_rule_messages():
    assert await errors_of({}) == {
        "password_confirmation": ["The password confirmation field is required."],
        "email": ["The email field is required."],
        "username": ["username is required but you provided None"],
        "password": ["The password field is required."],
    }


async def test_required_failure_stops_the_field():
    assert (await errors_of({**VALID, "username": ""}))["username"] == ["username is required but you provided ''"]


async def test_first_failing_rule_stops_the_field():
    assert (await errors_of({**VALID, "username": "ab"}))["username"] == [
        "The username field must be at least 3 characters."
    ]


async def test_missing_optional_field_skips_its_rules():
    assert (await RegisterUser.validate_input({**VALID, "nickname": ""})).nickname == ""


async def test_msg_replaces_last_rule_message():
    assert await errors_of({**VALID, "age": 17}) == {"age": ["Adults only."]}


async def test_custom_rule():
    assert await errors_of({**VALID, "captcha": "41"}) == {"captcha": ["The captcha is wrong."]}
    assert (await RegisterUser.validate_input({**VALID, "captcha": "42"})).captcha == "42"


async def test_cross_field_rules_see_fields_declared_later():
    errors = await errors_of({**VALID, "password_confirmation": "different", "is_business": True})

    assert errors == {
        "password_confirmation": ["The password confirmation field must match password."],
        "tax_id": ["The tax id field is required when is business is true."],
    }


async def test_type_errors_are_reported_with_rule_errors():
    errors = await errors_of({**VALID, "age": "old", "email": "nope", "is_business": "true"})

    assert errors == {
        "age": ["Input should be a valid integer, unable to parse string as an integer"],
        "email": ["The email field must be a valid email address."],
        "tax_id": ["The tax id field is required when is business is true."],
    }


async def test_plain_type_errors_are_reraised_unchanged_when_no_rule_fails():
    assert await errors_of({**VALID, "is_business": "maybe"}) == {
        "is_business": ["Input should be a valid boolean, unable to interpret input"]
    }


async def test_non_mapping_input_keeps_pydantic_error():
    assert await errors_of("not a dict") == {"": ["Input should be a valid dictionary or instance of RegisterUser"]}


async def test_field_without_nullable_rejects_none():
    class Profile(FormRequest):
        bio: Annotated[str, Field().max(5)] = "hi"

    assert await errors_of({"bio": None}, Profile) == {"bio": ["Input should be a valid string"]}


def test_field_rules_need_a_form_request():
    class Plain(BaseModel):
        name: Annotated[str, Field().required()]

    with pytest.raises(TypeError, match="FormRequest"):
        Plain.model_validate({"name": "jane"})


def test_rules_on_nested_models_raise_at_class_definition():
    class Address(BaseModel):
        code: Annotated[str, Field().required().min(5)]

    with pytest.raises(TypeError, match=r"Order\.address: validation rules on nested model Address"):

        class Order(FormRequest):
            address: Address

    with pytest.raises(TypeError, match=r"Shipment\.stops: validation rules on nested model Address"):

        class Shipment(FormRequest):
            stops: list[Address] | None = None


def test_nested_models_without_rules_are_allowed():
    class Address(BaseModel):
        code: str

    class Order(FormRequest):
        address: Address
        name: Annotated[str, Field().required()]

    assert Order.model_validate({"address": {"code": "ab"}, "name": "x"}).address.code == "ab"


async def test_numeric_fields_compare_size_by_value():
    class Payment(FormRequest):
        amount: Annotated[str, Field().required().max(10).numeric()]
        count: Annotated[str | None, Field().integer().between(1, 3)] = None

    assert (await Payment.validate_input({"amount": "9.5", "count": "2"})).amount == "9.5"
    assert await errors_of({"amount": "25", "count": "12"}, Payment) == {
        "amount": ["The amount field must not be greater than 10."],
        "count": ["The count field must be between 1 and 3."],
    }


async def test_in_rule_rejects_unhashable_values():
    class Pick(FormRequest):
        choice: Annotated[Any, Field().required().in_({"a", "b"})]

    assert await errors_of({"choice": ["a"]}, Pick) == {"choice": ["The selected choice is invalid."]}


def test_json_schema_keeps_required_fields_non_nullable():
    properties = RegisterUser.model_json_schema()["properties"]

    assert properties["email"] == {"title": "Email", "type": "string"}
    assert properties["nickname"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    assert properties["tax_id"]["anyOf"] == [{"type": "string"}, {"type": "null"}]


def test_msg_without_rule_raises():
    with pytest.raises(ValueError, match="needs a rule"):
        Field().msg("nothing to replace")


async def test_async_rules_run_in_the_same_pass_as_sync_rules():
    assert await errors_of({**VALID, "username": "admin", "email": "nope"}) == {
        "email": ["The email field must be a valid email address."],
        "username": ["The username admin is reserved."],
    }


async def test_validate_input_passes_context_to_rules():
    class Member(FormRequest):
        role: Annotated[str, Field().required().using(lambda attribute, value, data: data["team_id"] == 3)]

    assert (await Member.validate_input({"role": "x"}, {"team_id": 3})).role == "x"
    assert await errors_of({"role": "x"}, Member, {"team_id": 4}) == {"role": ["The role field is invalid."]}


async def test_closure_rules_can_be_sync_or_async():
    async def not_taken(attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        await asyncio.sleep(0)
        return value != "taken"

    class Profile(FormRequest):
        handle: Annotated[str, Field().required().using(not_taken, "The :attribute is taken.")]
        code: Annotated[str, Field().required().using(lambda attribute, value, data: value.isdigit())]

    assert (await Profile.validate_input({"handle": "free", "code": "12"})).code == "12"
    assert await errors_of({"handle": "taken", "code": "ab"}, Profile) == {
        "handle": ["The handle is taken."],
        "code": ["The code field is invalid."],
    }


async def test_rules_run_in_written_order_across_sync_and_async():
    calls: list[str] = []

    async def first(attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        calls.append("async")
        return False

    class Ordered(FormRequest):
        name: Annotated[str, Field().required().using(first).using(lambda *_: calls.append("sync") is None)]

    assert await errors_of({"name": "x"}, Ordered) == {"name": ["The name field is invalid."]}
    assert calls == ["async"]


async def test_stop_on_first_failure_stops_after_the_first_field():
    class Strict(FormRequest):
        stop_on_first_failure = True

        first: Annotated[str, Field().required()]
        second: Annotated[str, Field().required()]

    assert await errors_of({}, Strict) == {"first": ["The first field is required."]}


class Comment(FormRequest):
    body: Annotated[str, Field().required().min(3)]
    author: str = "guest"

    @classmethod
    async def authorize(cls, validator: Validator) -> bool:
        await asyncio.sleep(0)
        return validator.context.get("user") != "banned"

    @classmethod
    async def prepare_for_validation(cls, validator: Validator) -> None:
        await asyncio.sleep(0)
        validator.merge({"body": str(validator.data.get("body", "")).strip()})

    @classmethod
    async def after(cls, validator: Validator) -> None:
        await asyncio.sleep(0)
        if "spam" in str(validator.data.get("body")):
            validator.errors.add("body", "No spam.")
        if validator.data["author"] == validator.context.get("blocked"):
            validator.errors.add("author", "Blocked.")


async def test_async_authorize_rejects_before_reading_input():
    with pytest.raises(AuthorizationException) as caught:
        await Comment.validate_input("not even a dict", {"user": "banned"})

    assert caught.value.get_status() == 403
    assert caught.value.get_response() == "This action is unauthorized."


async def test_async_prepare_for_validation_changes_the_input():
    assert (await Comment.validate_input({"body": "  hello  "})).body == "hello"
    assert await errors_of({"body": "  hi  "}, Comment) == {"body": ["The body field must be at least 3 characters."]}


async def test_async_after_hook_adds_errors_with_validated_data():
    assert await errors_of({"body": "spam here"}, Comment, {"blocked": "guest"}) == {
        "body": ["No spam."],
        "author": ["Blocked."],
    }


async def test_sync_hooks_are_supported():
    class Sync(FormRequest):
        name: Annotated[str, Field().required()]

        @classmethod
        def authorize(cls, validator: Validator) -> bool:
            return validator.request is None

        @classmethod
        def prepare_for_validation(cls, validator: Validator) -> None:
            validator.merge({"name": "filled"})

        @classmethod
        def after(cls, validator: Validator) -> None:
            validator.errors.add("name", "After.") if validator.data["name"] != "filled" else None

    assert (await Sync.validate_input({})).name == "filled"


async def test_concurrent_validations_keep_their_own_errors():
    class Slow(FormRequest):
        name: Annotated[str, Field().required().using(lambda *_: asyncio.sleep(0.01, result=False))]
        team: Annotated[str, Field().required().using(lambda attribute, value, data: data["allowed"] == value)]

    results = await asyncio.gather(
        Slow.validate_input({"name": "a", "team": "x"}, {"allowed": "x"}),
        Slow.validate_input({"name": "", "team": "y"}, {"allowed": "x"}),
        Slow.validate_input({"name": "c", "team": "z"}, {"allowed": "z"}),
        return_exceptions=True,
    )

    assert [result.errors for result in results if isinstance(result, ValidationException)] == [
        {"name": ["The name field is invalid."]},
        {"name": ["The name field is required."], "team": ["The team field is invalid."]},
        {"name": ["The name field is invalid."]},
    ]


async def test_validate_input_accepts_a_model_instance():
    user = RegisterUser.model_validate(VALID)

    assert (await RegisterUser.validate_input(user)).username == "jane"
    assert await errors_of(RegisterUser.model_validate({**VALID, "username": "admin"})) == {
        "username": ["The username admin is reserved."]
    }


def test_model_validate_only_parses_types():
    user = RegisterUser.model_validate({**VALID, "username": "ab"})

    assert user.username == "ab"
    with pytest.raises(ValidationError):
        RegisterUser.model_validate({**VALID, "age": "old"})


def test_validation_exception_is_a_422_http_exception():
    exception = ValidationException({"name": ["The name field is required.", "Second."]})

    assert isinstance(exception, HttpException)
    assert exception.get_status() == 422
    assert exception.get_response() == "The name field is required. (and 1 more error)"
    assert str(exception) == "The name field is required. (and 1 more error)"
    assert exception.bag.messages == exception.errors


def test_builder_methods_append_their_rules():
    from fastapi_startkit.validation import rules

    field = Field().integer().numeric().boolean().between(1, 5).url().regex(r"\d").in_([1, 2]).not_in([3]).confirmed()

    assert [type(rule) for rule in field.rules] == [
        rules.Integer,
        rules.Numeric,
        rules.Boolean,
        rules.Between,
        rules.Url,
        rules.Regex,
        rules.In,
        rules.NotIn,
        rules.Confirmed,
    ]

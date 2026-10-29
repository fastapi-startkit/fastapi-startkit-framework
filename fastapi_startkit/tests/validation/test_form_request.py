from collections.abc import Mapping
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, ValidationError

from fastapi_startkit.exceptions import HttpException
from fastapi_startkit.validation import AsyncRule, Email, Field, FormRequest, MessageBag, Rule, ValidationException


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


def errors_of(data: dict[str, Any]) -> dict[str, list[str]]:
    with pytest.raises(ValidationError) as caught:
        RegisterUser.model_validate(data)
    return MessageBag.from_errors(caught.value.errors()).messages


def test_valid_data_builds_the_model():
    user = RegisterUser.model_validate({**VALID, "age": "20", "nickname": None})

    assert user.age == 20
    assert user.nickname is None
    assert user.tax_id is None


def test_missing_required_fields_use_rule_messages():
    assert errors_of({}) == {
        "password_confirmation": ["The password confirmation field is required."],
        "email": ["The email field is required."],
        "username": ["username is required but you provided None"],
        "password": ["The password field is required."],
    }


def test_required_failure_stops_the_field():
    assert errors_of({**VALID, "username": ""})["username"] == ["username is required but you provided ''"]


def test_first_failing_rule_stops_the_field():
    assert errors_of({**VALID, "username": "ab"})["username"] == ["The username field must be at least 3 characters."]


def test_missing_optional_field_skips_its_rules():
    assert RegisterUser.model_validate({**VALID, "nickname": ""}).nickname == ""


def test_msg_replaces_last_rule_message():
    assert errors_of({**VALID, "age": 17}) == {"age": ["Adults only."]}


def test_custom_rule():
    assert errors_of({**VALID, "captcha": "41"}) == {"captcha": ["The captcha is wrong."]}
    assert RegisterUser.model_validate({**VALID, "captcha": "42"}).captcha == "42"


def test_cross_field_rules_see_fields_declared_later():
    errors = errors_of({**VALID, "password_confirmation": "different", "is_business": True})

    assert errors == {
        "password_confirmation": ["The password confirmation field must match password."],
        "tax_id": ["The tax id field is required when is business is true."],
    }


def test_type_errors_are_reported_with_rule_errors():
    errors = errors_of({**VALID, "age": "old", "email": "nope", "is_business": "true"})

    assert errors == {
        "age": ["Input should be a valid integer, unable to parse string as an integer"],
        "email": ["The email field must be a valid email address."],
        "tax_id": ["The tax id field is required when is business is true."],
    }


def test_plain_type_errors_are_reraised_unchanged_when_no_rule_fails():
    assert errors_of({**VALID, "is_business": "maybe"}) == {
        "is_business": ["Input should be a valid boolean, unable to interpret input"]
    }


def test_non_mapping_input_keeps_pydantic_error():
    with pytest.raises(ValidationError) as caught:
        RegisterUser.model_validate("not a dict")

    assert [error["type"] for error in caught.value.errors()] == ["model_type"]


def test_field_without_nullable_rejects_none():
    class Profile(FormRequest):
        bio: Annotated[str, Field().max(5)] = "hi"

    with pytest.raises(ValidationError) as caught:
        Profile.model_validate({"bio": None})

    assert caught.value.errors()[0]["type"] == "string_type"


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


def test_numeric_fields_compare_size_by_value():
    class Payment(FormRequest):
        amount: Annotated[str, Field().required().max(10).numeric()]
        count: Annotated[str | None, Field().integer().between(1, 3)] = None

    assert Payment.model_validate({"amount": "9.5", "count": "2"}).amount == "9.5"
    with pytest.raises(ValidationError) as caught:
        Payment.model_validate({"amount": "25", "count": "12"})

    assert MessageBag.from_errors(caught.value.errors()).messages == {
        "amount": ["The amount field must not be greater than 10."],
        "count": ["The count field must be between 1 and 3."],
    }


def test_in_rule_rejects_unhashable_values():
    class Pick(FormRequest):
        choice: Annotated[Any, Field().required().in_({"a", "b"})]

    with pytest.raises(ValidationError) as caught:
        Pick.model_validate({"choice": ["a"]})

    assert MessageBag.from_errors(caught.value.errors()).messages == {"choice": ["The selected choice is invalid."]}


def test_json_schema_keeps_required_fields_non_nullable():
    properties = RegisterUser.model_json_schema()["properties"]

    assert properties["email"] == {"title": "Email", "type": "string"}
    assert properties["nickname"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    assert properties["tax_id"]["anyOf"] == [{"type": "string"}, {"type": "null"}]


def test_msg_without_rule_raises():
    with pytest.raises(ValueError, match="needs a rule"):
        Field().msg("nothing to replace")


async def test_validate_async_runs_async_rules():
    user = RegisterUser.model_validate({**VALID, "username": "admin"})

    with pytest.raises(ValidationException) as caught:
        await user.validate_async()

    assert caught.value.errors == {"username": ["The username admin is reserved."]}


async def test_validate_async_returns_model_when_rules_pass():
    user = RegisterUser.model_validate(VALID)

    assert await user.validate_async({"user_id": 1}) is user


async def test_validate_input_runs_both_phases():
    assert (await RegisterUser.validate_input(VALID)).username == "jane"

    with pytest.raises(ValidationException) as sync_failure:
        await RegisterUser.validate_input({**VALID, "email": "nope"})
    assert sync_failure.value.errors == {"email": ["The email field must be a valid email address."]}

    with pytest.raises(ValidationException) as async_failure:
        await RegisterUser.validate_input({**VALID, "username": "admin"})
    assert async_failure.value.errors == {"username": ["The username admin is reserved."]}


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

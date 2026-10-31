import tempfile
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Body, Depends
from pydantic import AliasChoices, AliasPath, ConfigDict
from pydantic import Field as PydanticField
from starlette.requests import Request as StarletteRequest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.validation import AsyncRule, Email, Field, FormRequest, Validated, Validator
from fastapi_startkit.validation.form_request import alias_keys, is_sequence, typed_path_params

TAKEN = {"jane@example.com": 1}
LOOKUPS: list[Any] = []


class UniqueEmail(AsyncRule):
    message = "The :attribute has already been taken."

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        LOOKUPS.append(data.get("user_id"))
        owner = TAKEN.get(value)
        return owner is None or owner == data.get("user_id")


class RegisterUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]
    username: Annotated[str, Field().required().string().min(3).max(10)]
    password: Annotated[str, Field().required().password()]
    password_confirmation: Annotated[str, Field().required().same_as("password")]


class UpdateUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]


class Request(FormRequest):
    email: Annotated[str, Email().required()]


TEAM_CONTEXT: list[dict[str, Any]] = []


class TeamMember(FormRequest):
    email: Annotated[str, Email().required()]

    @classmethod
    async def authorize(cls, validator: Validator) -> bool:
        TEAM_CONTEXT.append(dict(validator.context))
        return True


class Publish(FormRequest):
    title: Annotated[str, Field().required().min(3)]
    priority: int = 0

    @classmethod
    async def authorize(cls, validator: Validator) -> bool:
        return validator.request is not None and validator.request.headers.get("x-role") == "editor"


class Billing(FormRequest):
    name: Annotated[str, Field().required().min(3)]


class Shipping(FormRequest):
    name: Annotated[str, Field().required().min(5)]


class Listing(FormRequest):
    window: Annotated[str, Field().in_(["today", "week"])] = "today"
    q: Annotated[str, Field().string().max(5)] = ""
    page: Annotated[int, Field().integer().min(1)] = 1
    tags: list[str] = []
    archived: bool = False


class Search(FormRequest):
    term: Annotated[str, Field().required().min(2)]


class Transfer(FormRequest):
    to: Annotated[str, Field().required()]
    amount: Annotated[int, Field().required().min(1)]


class Profile(FormRequest):
    name: Annotated[str, Field().required()]
    role: str = "member"


class Paging(FormRequest):
    model_config = ConfigDict(populate_by_name=True)

    page_size: int = PydanticField(10, alias="pageSize")
    page: int = PydanticField(1, validation_alias=AliasChoices("p", "page"))


class Tagged(FormRequest):
    tags: Sequence[str] = ()
    ids: AbstractSet[int] | None = None
    q: str = ""


async def tenant(tenant_id: int) -> int:
    return tenant_id


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, providers=[FastAPIProvider])
    teams = APIRouter(prefix="/tenants/{tenant_id}/teams/{team_id}", dependencies=[Depends(tenant)])

    @teams.post("/members")
    async def add_member(team_id: int, data: Validated[TeamMember]):
        return {"email": data.email}

    app.fastapi.include_router(teams)

    @app.fastapi.post("/requests")
    async def request_model(data: Validated[Request]):
        return {"email": data.email}

    @app.fastapi.post("/register")
    async def register(data: Validated[RegisterUser]):
        return {"username": data.username}

    @app.fastapi.put("/users/{user_id}")
    async def update(user_id: int, data: Validated[UpdateUser]):
        return {"id": user_id, "email": data.email}

    @app.fastapi.post("/users/{user_id}/notes")
    async def note(user_id: int, data: Validated[UpdateUser], note: Annotated[str, Body()]):
        return {"id": user_id, "email": data.email, "note": note}

    @app.fastapi.post("/checkout")
    async def checkout(billing: Validated[Billing], shipping: Validated[Shipping]):
        return {"billing": billing.name, "shipping": shipping.name}

    @app.fastapi.post("/publish")
    async def publish(data: Validated[Publish]):
        return {"title": data.title}

    @app.fastapi.get("/listing")
    async def listing(query: Validated[Listing]):
        return query.model_dump()

    @app.fastapi.get("/search")
    async def search(query: Validated[Search]):
        return {"term": query.term}

    @app.fastapi.get("/users/{user_id}/email")
    async def check_email(user_id: int, query: Validated[UpdateUser]):
        return {"id": user_id, "email": query.email}

    @app.fastapi.get("/drafts")
    async def drafts(query: Validated[Publish]):
        return {"title": query.title}

    @app.fastapi.post("/search/billing")
    async def search_billing(query: Validated[Search], billing: Validated[Billing]):
        return {"term": query.term, "billing": billing.name}

    @app.fastapi.delete("/listing")
    async def clear_listing(query: Validated[Listing]):
        return query.model_dump()

    @app.fastapi.get("/search/listing")
    async def search_listing(search: Validated[Search], listing: Validated[Listing]):
        return {"term": search.term, "page": listing.page}

    @app.fastapi.get("/search/notes")
    async def search_notes(search: Validated[Search], note: Annotated[str | None, Body()] = None):
        return {"term": search.term, "note": note}

    @app.fastapi.get("/hidden", include_in_schema=False)
    async def hidden(query: Validated[Search]):
        return {"term": query.term}

    @app.fastapi.post("/transfer")
    async def transfer(data: Validated[Transfer]):
        return data.model_dump()

    @app.fastapi.patch("/profile")
    async def profile(data: Validated[Profile]):
        return {"set": sorted(data.model_fields_set), **data.model_dump()}

    @app.fastapi.get("/paging")
    async def paging(query: Validated[Paging]):
        return query.model_dump()

    @app.fastapi.get("/tagged")
    async def tagged(query: Validated[Tagged]):
        return {"tags": list(query.tags), "ids": sorted(query.ids or []), "q": query.q}

    @app.fastapi.post("/plain")
    async def plain(data: RegisterUser):
        return {"username": data.username}

    return app


JSON = {"accept": "application/json"}

VALID = {
    "email": "john@example.com",
    "username": "john",
    "password": "secret123",
    "password_confirmation": "secret123",
}


class FastAPIValidationTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            self._application = make_application(Path(self._tmp_dir.name))
        return self._application

    async def test_valid_request_reaches_the_endpoint(self):
        response = await self.post("/register", json=VALID)

        response.assert_status(200)
        self.assertEqual(response.json(), {"username": "john"})

    async def test_sync_rule_failures_return_laravel_shape(self):
        response = await self.post("/register", json={"email": "nope", "username": "jo", "password": "secret123"})

        response.assert_status(422)
        self.assertEqual(
            response.json(),
            {
                "message": "The email field must be a valid email address. (and 2 more errors)",
                "errors": {
                    "email": ["The email field must be a valid email address."],
                    "username": ["The username field must be at least 3 characters."],
                    "password_confirmation": ["The password confirmation field is required."],
                },
            },
        )

    async def test_async_rule_failures_return_laravel_shape(self):
        response = await self.post("/register", json={**VALID, "email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(
            response.json(),
            {
                "message": "The email has already been taken.",
                "errors": {"email": ["The email has already been taken."]},
            },
        )

    async def test_path_parameters_are_validation_context(self):
        own = await self.put("/users/1", json={"email": "jane@example.com"})
        other = await self.put("/users/2", json={"email": "jane@example.com"})

        own.assert_status(200)
        self.assertEqual(own.json(), {"id": 1, "email": "jane@example.com"})
        other.assert_status(422)
        self.assertEqual(other.json()["errors"], {"email": ["The email has already been taken."]})

    async def test_invalid_path_parameter_is_reported_before_async_rules(self):
        LOOKUPS.clear()

        response = await self.put("/users/abc", json={"email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), ["user_id"])
        self.assertEqual(LOOKUPS, [])

    async def test_validated_body_is_embedded_under_the_model_name_with_other_body_params(self):
        valid = await self.post("/users/1/notes", json={"update_user": {"email": "jane@example.com"}, "note": "hi"})
        taken = await self.post("/users/2/notes", json={"update_user": {"email": "jane@example.com"}, "note": "hi"})
        schema = (await self.get("/openapi.json")).json()
        body = schema["components"]["schemas"]["Body_note_users__user_id__notes_post"]

        valid.assert_status(200)
        self.assertEqual(valid.json(), {"id": 1, "email": "jane@example.com", "note": "hi"})
        taken.assert_status(422)
        self.assertEqual(taken.json()["errors"], {"update_user.email": ["The email has already been taken."]})
        self.assertEqual(sorted(body["properties"]), ["note", "update_user"])

    async def test_multiple_validated_params_are_combined_under_their_embed_keys(self):
        both = await self.post("/checkout", json={"billing": {"name": "a"}, "shipping": {"name": "ab"}})
        second = await self.post("/checkout", json={"billing": {"name": "abcd"}, "shipping": {"name": "ab"}})
        valid = await self.post("/checkout", json={"billing": {"name": "abcd"}, "shipping": {"name": "abcdef"}})

        both.assert_status(422)
        self.assertEqual(
            both.json(),
            {
                "message": "The name field must be at least 3 characters. (and 1 more error)",
                "errors": {
                    "billing.name": ["The name field must be at least 3 characters."],
                    "shipping.name": ["The name field must be at least 5 characters."],
                },
            },
        )
        second.assert_status(422)
        self.assertEqual(second.json()["errors"], {"shipping.name": ["The name field must be at least 5 characters."]})
        valid.assert_status(200)
        self.assertEqual(valid.json(), {"billing": "abcd", "shipping": "abcdef"})

    async def test_missing_embedded_body_runs_its_required_rules(self):
        response = await self.post("/checkout", json={"billing": {"name": "a"}})

        response.assert_status(422)
        self.assertEqual(
            response.json()["errors"],
            {
                "billing.name": ["The name field must be at least 3 characters."],
                "shipping.name": ["The name field is required."],
            },
        )

    async def test_multiple_validated_params_keep_the_embedded_openapi_schema(self):
        schema = (await self.get("/openapi.json")).json()
        body = schema["components"]["schemas"]["Body_checkout_checkout_post"]

        self.assertEqual(
            body["properties"],
            {
                "billing": {"$ref": "#/components/schemas/Billing"},
                "shipping": {"$ref": "#/components/schemas/Shipping"},
            },
        )
        self.assertNotIn("required", body)

    async def test_plain_body_parameter_only_parses_types(self):
        accepted = await self.post("/plain", json={**VALID, "username": "jo"})
        rejected = await self.post("/plain", json={**VALID, "username": 5})

        accepted.assert_status(200)
        rejected.assert_status(422)
        self.assertEqual(rejected.json()["errors"], {"username": ["Input should be a valid string"]})

    async def test_type_errors_and_rule_errors_share_one_response(self):
        response = await self.post("/publish", json={"title": "ab", "priority": "high"}, headers={"x-role": "editor"})

        response.assert_status(422)
        self.assertEqual(
            response.json()["errors"],
            {
                "priority": ["Input should be a valid integer, unable to parse string as an integer"],
                "title": ["The title field must be at least 3 characters."],
            },
        )

    async def test_async_authorize_reads_the_request(self):
        allowed = await self.post("/publish", json={"title": "News"}, headers={"x-role": "editor"})
        denied = await self.post("/publish", json={"title": "News"}, headers={"x-role": "viewer"})

        allowed.assert_status(200)
        self.assertEqual(allowed.json(), {"title": "News"})
        denied.assert_status(403)

    async def test_missing_body_is_reported(self):
        response = await self.post("/register", headers=JSON)

        response.assert_status(422)
        self.assertEqual(response.json()["errors"], {"": ["Field required"]})

    async def test_missing_embedded_bodies_are_reported_under_their_keys(self):
        response = await self.post("/checkout", headers=JSON)

        response.assert_status(422)
        self.assertEqual(response.json()["errors"], {"billing": ["Field required"], "shipping": ["Field required"]})

    async def test_openapi_keeps_the_request_body_schema(self):
        schema = (await self.get("/openapi.json")).json()
        body = schema["paths"]["/register"]["post"]["requestBody"]["content"]["application/json"]["schema"]

        self.assertEqual(body, {"$ref": "#/components/schemas/RegisterUser"})

    async def test_router_prefix_and_dependency_path_params_are_typed_context(self):
        TEAM_CONTEXT.clear()

        valid = await self.post("/tenants/7/teams/3/members", json={"email": "a@example.com"})
        invalid = await self.post("/tenants/x/teams/3/members", json={"email": "a@example.com"})

        valid.assert_status(200)
        invalid.assert_status(422)
        self.assertEqual(TEAM_CONTEXT, [{"tenant_id": 7, "team_id": 3}])

    async def test_form_request_named_request_does_not_collide_with_the_http_request(self):
        response = await self.post("/requests", json={"email": "a@example.com"})

        response.assert_status(200)
        self.assertEqual(response.json(), {"email": "a@example.com"})

    async def test_validated_applies_model_defaults_when_no_parameter_is_given(self):
        response = await self.get("/listing", headers=JSON)

        response.assert_status(200)
        self.assertEqual(response.json(), {"window": "today", "q": "", "page": 1, "tags": [], "archived": False})

    async def test_validated_coerces_query_strings_and_repeated_keys(self):
        response = await self.get("/listing?window=week&q=abc&page=2&archived=1&tags=a&tags=b", headers=JSON)

        response.assert_status(200)
        self.assertEqual(
            response.json(), {"window": "week", "q": "abc", "page": 2, "tags": ["a", "b"], "archived": True}
        )

    async def test_validated_rule_failures_return_laravel_shape(self):
        response = await self.get("/listing?window=year&q=toolong&page=0", headers=JSON)

        response.assert_status(422)
        self.assertEqual(
            response.json()["errors"],
            {
                "window": ["The selected window is invalid."],
                "q": ["The q field must not be greater than 5 characters."],
                "page": ["The page field must be at least 1."],
            },
        )

    async def test_validated_type_errors_and_rule_errors_share_one_response(self):
        response = await self.get("/listing?page=abc&q=toolong", headers=JSON)

        response.assert_status(422)
        self.assertEqual(
            response.json()["errors"],
            {
                "page": ["Input should be a valid integer, unable to parse string as an integer"],
                "q": ["The q field must not be greater than 5 characters."],
            },
        )

    async def test_validated_reports_a_missing_required_parameter_with_the_rule_message(self):
        response = await self.get("/search", headers=JSON)

        response.assert_status(422)
        self.assertEqual(response.json()["errors"], {"term": ["The term field is required."]})

    async def test_validated_receives_path_parameters_as_context(self):
        own = await self.get("/users/1/email?email=jane@example.com", headers=JSON)
        other = await self.get("/users/2/email?email=jane@example.com", headers=JSON)

        own.assert_status(200)
        self.assertEqual(own.json(), {"id": 1, "email": "jane@example.com"})
        other.assert_status(422)
        self.assertEqual(other.json()["errors"], {"email": ["The email has already been taken."]})

    async def test_validated_runs_authorize(self):
        allowed = await self.get("/drafts?title=News", headers={**JSON, "x-role": "editor"})
        denied = await self.get("/drafts?title=News", headers={**JSON, "x-role": "viewer"})

        allowed.assert_status(200)
        self.assertEqual(allowed.json(), {"title": "News"})
        denied.assert_status(403)

    async def test_validated_and_validated_body_errors_are_combined(self):
        valid = await self.post("/search/billing?term=paris", json={"billing": {"name": "abcd"}})
        invalid = await self.post("/search/billing?term=p", json={"billing": {"name": "a"}}, headers=JSON)

        valid.assert_status(200)
        self.assertEqual(valid.json(), {"term": "paris", "billing": "abcd"})
        invalid.assert_status(422)
        self.assertEqual(
            invalid.json()["errors"],
            {
                "search.term": ["The term field must be at least 2 characters."],
                "billing.name": ["The name field must be at least 3 characters."],
            },
        )

    async def test_body_values_override_query_values_of_the_same_field(self):
        response = await self.post("/requests?email=query@example.com", json={"email": "body@example.com"})

        response.assert_status(200)
        self.assertEqual(response.json(), {"email": "body@example.com"})

    async def test_query_values_fill_fields_missing_from_the_body(self):
        response = await self.post("/requests?email=query@example.com", json={})

        response.assert_status(200)
        self.assertEqual(response.json(), {"email": "query@example.com"})

    async def test_openapi_documents_the_request_body_as_optional(self):
        schema = (await self.get("/openapi.json")).json()
        body = schema["paths"]["/register"]["post"]["requestBody"]

        self.assertFalse(body.get("required", False))

    async def test_bodyless_cross_site_post_does_not_validate_the_query(self):
        for content_type in ("application/x-www-form-urlencoded", "text/plain", None):
            headers = {**JSON, "content-type": content_type} if content_type else JSON
            response = await self.post("/transfer?to=attacker&amount=100", headers=headers)

            response.assert_status(422)
            self.assertEqual(response.json()["errors"], {"": ["Field required"]})

    async def test_bodyless_put_and_patch_report_the_missing_body(self):
        put = await self.put("/users/1?email=jane@example.com", headers=JSON)
        patch = await self.patch("/profile?name=n", headers=JSON)

        put.assert_status(422)
        self.assertEqual(put.json()["errors"], {"": ["Field required"]})
        patch.assert_status(422)
        self.assertEqual(patch.json()["errors"], {"": ["Field required"]})

    async def test_non_form_body_is_rejected_even_with_a_valid_query(self):
        response = await self.post(
            "/transfer?to=attacker&amount=100", content=b"to=attacker", headers={**JSON, "content-type": "text/plain"}
        )

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), [""])

    async def test_json_body_is_merged_with_the_query_on_write_methods(self):
        response = await self.post("/transfer?to=friend", json={"amount": 5})

        response.assert_status(200)
        self.assertEqual(response.json(), {"to": "friend", "amount": 5})

    async def test_query_values_of_declared_fields_are_set_on_write_methods(self):
        response = await self.patch("/profile?role=admin&unknown=1", json={"name": "n"})

        response.assert_status(200)
        self.assertEqual(response.json(), {"set": ["name", "role"], "name": "n", "role": "admin"})

    async def test_json_null_body_is_rejected_as_a_non_object_body(self):
        post = await self.post(
            "/requests?email=query@example.com", content=b"null", headers={**JSON, "content-type": "application/json"}
        )
        get = await self.client.request(
            "GET", "/search?term=paris", content=b"null", headers={**JSON, "content-type": "application/json"}
        )

        post.assert_status(422)
        self.assertEqual(list(post.json()["errors"]), [""])
        self.assertEqual(get.status_code, 422)
        self.assertEqual(list(get.json()["errors"]), [""])

    async def test_non_object_body_is_rejected_even_with_a_valid_query(self):
        response = await self.post("/requests?email=query@example.com", json=[1], headers=JSON)

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), [""])

    async def test_bodyless_delete_validates_the_query(self):
        response = await self.delete("/listing?page=3&tags=a&tags=b", headers=JSON)

        response.assert_status(200)
        self.assertEqual(
            response.json(), {"window": "today", "q": "", "page": 3, "tags": ["a", "b"], "archived": False}
        )

    async def test_query_reads_aliases_alias_choices_and_names_when_populate_by_name(self):
        by_name = await self.get("/paging?page_size=5&p=3", headers=JSON)
        by_alias = await self.get("/paging?pageSize=7&page=2", headers=JSON)

        by_name.assert_status(200)
        self.assertEqual(by_name.json(), {"page_size": 5, "page": 3})
        by_alias.assert_status(200)
        self.assertEqual(by_alias.json(), {"page_size": 7, "page": 2})

    async def test_abstract_sequences_and_sets_receive_every_repeated_value(self):
        response = await self.get("/tagged?tags=a&tags=b&ids=1&ids=2&q=x&q=y", headers=JSON)

        response.assert_status(200)
        self.assertEqual(response.json(), {"tags": ["a", "b"], "ids": [1, 2], "q": "y"})

    async def test_embedded_query_models_each_read_the_query(self):
        response = await self.get("/search/listing?term=paris&page=2", headers=JSON)

        response.assert_status(200)
        self.assertEqual(response.json(), {"term": "paris", "page": 2})

    async def test_openapi_documents_query_parameters_on_query_methods(self):
        schema = (await self.get("/openapi.json")).json()
        listing = schema["paths"]["/listing"]
        search_listing = schema["paths"]["/search/listing"]["get"]

        for operation in (listing["get"], listing["delete"]):
            self.assertNotIn("requestBody", operation)
            self.assertEqual(
                {item["name"]: (item["in"], item["required"]) for item in operation["parameters"]},
                {name: ("query", False) for name in ("window", "q", "page", "tags", "archived")},
            )
        self.assertEqual(listing["get"]["parameters"][3]["schema"]["type"], "array")
        self.assertNotIn("requestBody", search_listing)
        self.assertEqual(
            [(item["name"], item["required"]) for item in search_listing["parameters"]],
            [("term", True), ("window", False), ("q", False), ("page", False), ("tags", False), ("archived", False)],
        )

    async def test_openapi_documents_path_and_query_parameters_together(self):
        schema = (await self.get("/openapi.json")).json()
        operation = schema["paths"]["/users/{user_id}/email"]["get"]

        self.assertEqual(
            [(item["name"], item["in"]) for item in operation["parameters"]], [("user_id", "path"), ("email", "query")]
        )

    async def test_openapi_keeps_the_body_on_write_methods_and_mixed_bodies(self):
        schema = (await self.get("/openapi.json")).json()

        self.assertIn("requestBody", schema["paths"]["/transfer"]["post"])
        self.assertNotIn("parameters", schema["paths"]["/transfer"]["post"])
        self.assertIn("requestBody", schema["paths"]["/search/notes"]["get"])
        self.assertNotIn("/hidden", schema["paths"])


def test_path_params_without_a_matched_route_stay_raw():
    request = StarletteRequest({"type": "http", "path_params": {"user_id": "1"}})

    assert typed_path_params(request) == {"user_id": "1"}


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (list[str], True),
        (Sequence[str], True),
        (AbstractSet[int] | None, True),
        (Annotated[tuple[int, ...], "meta"] | None, True),
        (list, True),
        (str, False),
        (bytes | None, False),
        (dict[str, int], False),
        (int, False),
    ],
)
def test_is_sequence(annotation: Any, expected: bool):
    assert is_sequence(annotation) is expected


def test_alias_keys_keeps_single_key_aliases():
    alias = AliasChoices("p", AliasPath("page"), AliasPath("filter", "page"))

    assert list(alias_keys(alias)) == ["p", "page"]
    assert list(alias_keys(None)) == []

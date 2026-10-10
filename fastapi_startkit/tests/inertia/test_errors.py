import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from starlette.middleware.sessions import SessionMiddleware

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.errors import ValidationErrors, flash_errors, shape_error_bags
from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.middleware import InertiaMiddleware
from fastapi_startkit.inertia.session import InertiaSessionWarning


class Form(BaseModel):
    email: str
    age: int


def build_app(with_session: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(InertiaMiddleware)
    if with_session:
        app.add_middleware(SessionMiddleware, secret_key="secret")

    @app.post("/back-with-errors")
    def back_with_errors():
        return Inertia.back_with_errors({"email": ["Required"]})

    @app.post("/back-with-errors-bag")
    def back_with_errors_bag():
        return Inertia.back_with_errors({"password": ["Too short"]}, bag="login")

    @app.post("/back-with-errors-header")
    def back_with_errors_header():
        return Inertia.back_with_errors({"password": ["Too short"]})

    @app.post("/render-with-errors")
    def render_with_errors():
        return Inertia.render("Users/Form").with_errors({"email": ["Required", "Invalid"]})

    @app.post("/render-with-errors-in")
    def render_with_errors_in():
        return Inertia.render("Users/Form").with_errors_in("login", {"password": ["Too short"]})

    @app.post("/render-with-errors-header")
    def render_with_errors_header():
        return Inertia.render("Users/Form").with_errors({"email": ["Required"]})

    @app.get("/page")
    def page():
        return Inertia.render("Users/Index")

    return app


class TestValidationErrors(unittest.TestCase):
    def test_add_and_get_collect_messages_per_field(self):
        errors = ValidationErrors().add("email", "Required").add("email", "Invalid")

        self.assertEqual(errors.get("email"), ["Required", "Invalid"])

    def test_has_reports_fields_with_messages(self):
        errors = ValidationErrors({"email": ["Required"]})

        self.assertTrue(errors.has("email"))
        self.assertFalse(errors.has("name"))

    def test_get_missing_field_returns_empty_list(self):
        self.assertEqual(ValidationErrors().get("name"), [])

    def test_first_returns_first_message_or_none(self):
        errors = ValidationErrors({"email": ["Required", "Invalid"]})

        self.assertEqual(errors.first("email"), "Required")
        self.assertIsNone(errors.first("name"))

    def test_merge_combines_without_mutating_either_side(self):
        left = ValidationErrors({"email": ["Required"]})
        right = ValidationErrors({"email": ["Invalid"], "name": ["Required"]})

        merged = left.merge(right)

        self.assertEqual(merged.to_dict(), {"email": ["Required", "Invalid"], "name": ["Required"]})
        self.assertEqual(left.to_dict(), {"email": ["Required"]})

    def test_string_messages_are_normalised_to_lists(self):
        self.assertEqual(ValidationErrors({"email": "Required"}).to_dict(), {"email": ["Required"]})

    def test_from_pydantic_validation_error(self):
        with self.assertRaises(ValidationError) as raised:
            Form(email=None, age="many")

        errors = ValidationErrors.from_validation_error(raised.exception)

        self.assertTrue(errors.has("email"))
        self.assertTrue(errors.has("age"))

    def test_from_request_validation_error_drops_location(self):
        exc = RequestValidationError([{"loc": ("body", "user", "email"), "msg": "field required", "type": "missing"}])

        self.assertEqual(ValidationErrors.from_validation_error(exc).to_dict(), {"user.email": ["field required"]})


class TestFlashErrors(unittest.TestCase):
    def test_flashing_keeps_errors_already_in_session(self):
        session = {"errors": {"default": {"email": ["Required"]}}}

        flash_errors(session, "login", ValidationErrors({"password": ["Too short"]}))
        flash_errors(session, "default", ValidationErrors({"email": ["Invalid"]}))

        self.assertEqual(
            session["errors"],
            {"default": {"email": ["Required", "Invalid"]}, "login": {"password": ["Too short"]}},
        )


class TestShapeErrorBags(unittest.TestCase):
    def test_default_bag_is_flat_with_first_message(self):
        shaped = shape_error_bags({"default": {"email": ["Required", "Invalid"]}}, with_all_errors=False)

        self.assertEqual(shaped, {"email": "Required"})

    def test_default_bag_keeps_all_messages_when_enabled(self):
        shaped = shape_error_bags({"default": {"email": ["Required", "Invalid"]}}, with_all_errors=True)

        self.assertEqual(shaped, {"email": ["Required", "Invalid"]})

    def test_named_bag_is_nested(self):
        shaped = shape_error_bags({"login": {"password": ["Too short"]}}, with_all_errors=False)

        self.assertEqual(shaped, {"login": {"password": "Too short"}})

    def test_default_and_named_bags_coexist(self):
        shaped = shape_error_bags(
            {"default": {"email": ["Required"]}, "login": {"password": ["Too short"]}},
            with_all_errors=False,
        )

        self.assertEqual(shaped, {"email": "Required", "login": {"password": "Too short"}})


class TestInertiaErrors(unittest.TestCase):
    def setUp(self):
        Inertia._instance = None
        container_patch = patch("fastapi_startkit.application.app")
        mock_app_getter = container_patch.start()
        self.addCleanup(container_patch.stop)
        mock_app_getter.return_value = MagicMock(has=MagicMock(return_value=False))

    def page_errors(self, client: TestClient):
        return client.get("/page", headers={Header.INERTIA: "true"}).json()["props"]["errors"]

    def test_back_with_errors_default_bag_reaches_next_page(self):
        client = TestClient(build_app())

        client.post("/back-with-errors", follow_redirects=False)

        self.assertEqual(self.page_errors(client), {"email": "Required"})

    def test_back_with_errors_explicit_bag_is_nested(self):
        client = TestClient(build_app())

        client.post("/back-with-errors-bag", follow_redirects=False)

        self.assertEqual(self.page_errors(client), {"login": {"password": "Too short"}})

    def test_back_with_errors_honours_error_bag_header(self):
        client = TestClient(build_app())

        client.post("/back-with-errors-header", headers={Header.ERROR_BAG: "login"}, follow_redirects=False)

        self.assertEqual(self.page_errors(client), {"login": {"password": "Too short"}})

    def test_back_with_errors_clears_after_next_page(self):
        client = TestClient(build_app())

        client.post("/back-with-errors", follow_redirects=False)
        self.page_errors(client)

        self.assertEqual(self.page_errors(client), {})

    def test_back_with_errors_without_session_warns_instead_of_raising(self):
        client = TestClient(build_app(with_session=False))

        with self.assertWarns(InertiaSessionWarning):
            response = client.post("/back-with-errors", follow_redirects=False)

        self.assertEqual(response.status_code, 302)

    def test_back_outside_request_raises(self):
        with self.assertRaises(RuntimeError):
            Inertia.back()

    def test_render_with_errors_uses_first_message(self):
        client = TestClient(build_app())

        response = client.post("/render-with-errors", headers={Header.INERTIA: "true"})

        self.assertEqual(response.json()["props"]["errors"], {"email": "Required"})

    def test_render_with_all_errors_keeps_every_message(self):
        Inertia.with_all_errors(True)
        client = TestClient(build_app())

        response = client.post("/render-with-errors", headers={Header.INERTIA: "true"})

        self.assertEqual(response.json()["props"]["errors"], {"email": ["Required", "Invalid"]})

    def test_render_with_errors_in_nests_under_bag(self):
        client = TestClient(build_app())

        response = client.post("/render-with-errors-in", headers={Header.INERTIA: "true"})

        self.assertEqual(response.json()["props"]["errors"], {"login": {"password": "Too short"}})

    def test_render_with_errors_honours_error_bag_header(self):
        client = TestClient(build_app())

        response = client.post(
            "/render-with-errors-header",
            headers={Header.INERTIA: "true", Header.ERROR_BAG: "login"},
        )

        self.assertEqual(response.json()["props"]["errors"], {"login": {"email": "Required"}})

    def test_explicit_bag_overrides_error_bag_header(self):
        client = TestClient(build_app())

        response = client.post(
            "/render-with-errors-in",
            headers={Header.INERTIA: "true", Header.ERROR_BAG: "other"},
        )

        self.assertEqual(response.json()["props"]["errors"], {"login": {"password": "Too short"}})

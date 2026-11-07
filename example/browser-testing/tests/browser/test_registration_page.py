from app.models.user import User
from databases.factories.user_factory import UserFactory
from fastapi_startkit.application import app
from fastapi_startkit.masoniteorm.testing import DatabaseTruncation
from fastapi_startkit.playwright import visit

from .test_case import TestCase


class TestRegistration(TestCase, DatabaseTruncation):
    async def test_user_can_sign_in(self) -> None:
        user = await UserFactory.new().create(email="nuno@laravel.com", password="password")

        await (
            visit("/register")
            .on()
            .mobile()
            .firefox()
            .click("Sign In")
            .assert_url_is("/login")
            .assert_see("Sign in to your account")
            .fill("email", "nuno@laravel.com")
            .fill("password", "password")
            .click("submit")
            .assert_url_is("/dashboard")
            .assert_see(f"Welcome back, {user.name}")
        )

        sessions = app().make("db").connection().query().table("sessions")
        assert await sessions.where("user_id", str(user.id)).count() == 1

    async def test_new_user_can_create_an_account(self) -> None:
        await (
            visit("/register")
            .fill("name", "Ada Lovelace")
            .fill("email", "ada@example.com")
            .fill("password", "analytical-engine")
            .click("Create account")
            .assert_url_is("/dashboard")
            .assert_see("Welcome back, Ada Lovelace")
        )

        user = await User.where("email", "ada@example.com").first()
        assert user is not None
        assert user.name == "Ada Lovelace"
        assert user.password != "analytical-engine"

    async def test_wrong_password_is_rejected(self) -> None:
        await UserFactory.new().create(email="nuno@laravel.com", password="password")

        await (
            visit("/login")
            .fill("email", "nuno@laravel.com")
            .fill("password", "not-the-password")
            .click("submit")
            .assert_see("These credentials do not match our records.")
            .assert_url_is("/login")
        )

    async def test_an_email_can_only_register_once(self) -> None:
        await UserFactory.new().create(email="nuno@laravel.com")

        await (
            visit("/register")
            .fill("name", "Someone Else")
            .fill("email", "nuno@laravel.com")
            .fill("password", "another-password")
            .click("Create account")
            .assert_see("The email has already been taken.")
            .assert_url_is("/register")
        )

        assert await User.where("email", "nuno@laravel.com").count() == 1

    async def test_user_can_log_out(self) -> None:
        await UserFactory.new().create(email="nuno@laravel.com", password="password")

        await (
            visit("/login")
            .fill("email", "nuno@laravel.com")
            .fill("password", "password")
            .click("submit")
            .assert_url_is("/dashboard")
            .click("Log out")
            .assert_url_is("/login")
            .navigate("/dashboard")
            .assert_url_is("/login")
        )

    async def test_guests_are_redirected_to_login(self) -> None:
        await visit("/dashboard").assert_path_is("/login").assert_see("Sign in to your account")

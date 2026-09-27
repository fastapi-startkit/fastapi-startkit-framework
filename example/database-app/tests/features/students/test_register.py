from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm.testing import RefreshDatabase

from app.models.user import User
from tests.test_case import TestCase


class TestRegister(TestCase, HttpTestCase, RefreshDatabase):
    async def test_user_can_register(self):
        response = await self.post(
            "/students/register",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Student registered successfully"
        assert "user_id" in response.json()

        user = await User.where("email", "john@example.com").first()
        assert user is not None
        assert user.name == "John Doe"
        assert user.role == "student"

    async def test_user_cannot_register_with_invalid_data(self):
        # missing required fields
        response = await self.post("/students/register", json={})
        assert response.status_code == 422

        # password to shorts
        response = await self.post(
            "/students/register",
            json={
                "name": "John Doe",
                "email": "john@example.com",
                "password": "short",
            },
        )
        assert response.status_code == 422

        # invalid email
        response = await self.post(
            "/students/register",
            json={
                "name": "John Doe",
                "email": "not-an-email",
                "password": "password123",
            },
        )
        assert response.status_code == 422

        # name too shorts
        response = await self.post(
            "/students/register",
            json={
                "name": "J",
                "email": "john@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 422

    async def test_user_cannot_register_with_duplicate_email(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "password123",
        }

        await self.post("/students/register", json=payload)

        response = await self.post("/students/register", json=payload)
        assert response.status_code == 422
        errors = response.json()["errors"]
        assert "email" in errors

from fastapi_startkit.fastapi.testing import HttpTestCase

from tests.test_case import TestCase


class TestWebRoutes(TestCase, HttpTestCase):
    async def test_health_endpoint_returns_ok(self):
        response = await self.get("/api/health")

        response.assert_ok()
        assert response.json() == {"status": "healthy"}

    async def test_index_page_renders(self):
        response = await self.get("/")

        response.assert_ok()
        body = response.text
        assert "FastAPI StartKit" in body
        assert "/build/assets/" in body
        assert "{{ vite" not in body

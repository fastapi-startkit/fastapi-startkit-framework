from pathlib import Path

from fastapi_startkit.fastapi.testing import HttpTestCase

from tests.test_case import TestCase


class TestWebRoutes(TestCase, HttpTestCase):
    async def test_health_endpoint_returns_ok(self):
        response = await self.get("/api/health")

        response.assert_ok()
        assert response.json() == {"status": "healthy"}

    async def test_index_page_renders(self):
        # vite() needs a built manifest or the dev-server hot file; write the
        # hot file (Vite reads public/hot relative to the cwd) so the template's
        # vite('resources/js/app.ts') directive resolves in dev mode.
        hot_file = Path("public") / "hot"
        hot_file.parent.mkdir(parents=True, exist_ok=True)
        hot_file.write_text("http://localhost:5173")
        try:
            response = await self.get("/")
        finally:
            hot_file.unlink(missing_ok=True)

        response.assert_ok()
        body = response.text
        assert "FastAPI StartKit" in body
        assert "resources/js/app.ts" in body
        assert "{{ vite" not in body

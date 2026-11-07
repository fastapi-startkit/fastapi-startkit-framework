from fastapi_startkit.fastapi.testing import HttpTestCase


class TestApplication(HttpTestCase):
    def get_application(self):
        from bootstrap.application import app

        return app

    async def test_health(self):
        response = await self.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

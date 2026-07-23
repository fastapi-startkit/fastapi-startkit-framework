from abc import ABC

from fastapi_startkit.fastapi.testing.test_response import TestResponse
from fastapi_startkit.testing import TestCase
from httpx import AsyncClient, ASGITransport


class HttpTestCase(TestCase, ABC):
    client: AsyncClient

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self._client_ctx = AsyncClient(
            transport=ASGITransport(app=self.get_application().fastapi), base_url="http://test"
        )
        self.client = await self._client_ctx.__aenter__()

    async def asyncTearDown(self):
        await self._client_ctx.__aexit__(None, None, None)
        await super().asyncTearDown()

    async def get(self, url, **kwargs) -> TestResponse:
        return TestResponse(await self.client.get(url, **kwargs))

    async def post(self, url, **kwargs) -> TestResponse:
        return TestResponse(await self.client.post(url, **kwargs))

    async def put(self, url, **kwargs) -> TestResponse:
        return TestResponse(await self.client.put(url, **kwargs))

    async def patch(self, url, **kwargs) -> TestResponse:
        return TestResponse(await self.client.patch(url, **kwargs))

    async def delete(self, url, **kwargs) -> TestResponse:
        return TestResponse(await self.client.delete(url, **kwargs))

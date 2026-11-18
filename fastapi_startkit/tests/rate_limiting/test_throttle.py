import tempfile
from pathlib import Path
from unittest import mock

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.rate_limiting import Limit, LimiterNotDefinedException, RateLimiterProvider, throttle

START = 1_000_000.0


async def ip(request: Request) -> Limit:
    return Limit.per_minute(2).by(request.headers.get("x-user", ""))


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, providers=[FastAPIProvider, RateLimiterProvider])
    limiter = app.make("rate_limiter")
    limiter.for_("login", lambda request: Limit.per_minute(2).by(request.client.host))
    limiter.for_("users", ip)
    limiter.for_("layered", lambda request: [Limit.per_minute(3), Limit.per_second(1)])
    limiter.for_("open", lambda request: Limit.none())
    limiter.for_(
        "custom",
        lambda request: Limit.per_minute(1).response(
            lambda request, headers: JSONResponse({"message": "slow down"}, status_code=429, headers=headers)
        ),
    )

    async def custom_async(request, headers):
        return JSONResponse({"message": "later"}, status_code=503)

    limiter.for_("custom-async", lambda request: Limit.per_minute(1).response(custom_async))

    for name in ("login", "users", "layered", "open", "custom", "custom-async", "missing"):
        app.fastapi.get(f"/{name}", dependencies=[Depends(throttle(name))])(lambda: {"ok": True})
    app.fastapi.get("/global", dependencies=[Depends(throttle(max_attempts=1))])(lambda: {"ok": True})
    return app


class ThrottleTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            self._application = make_application(Path(self._tmp_dir.name))
        return self._application

    async def asyncSetUp(self):
        self.clock = self.enterContext(mock.patch("time.time", return_value=START))
        await super().asyncSetUp()

    async def test_sets_rate_limit_headers(self):
        first = await self.get("/login")
        second = await self.get("/login")

        first.assert_status(200)
        self.assertEqual(first.headers["X-RateLimit-Limit"], "2")
        self.assertEqual(first.headers["X-RateLimit-Remaining"], "1")
        self.assertEqual(second.headers["X-RateLimit-Remaining"], "0")

    async def test_returns_429_with_retry_after_when_exceeded(self):
        await self.get("/login")
        await self.get("/login")
        self.clock.return_value += 20

        response = await self.get("/login")

        response.assert_status(429)
        self.assertEqual(response.headers["Retry-After"], "40")
        self.assertEqual(response.headers["X-RateLimit-Limit"], "2")
        self.assertEqual(response.headers["X-RateLimit-Remaining"], "0")
        self.assertEqual(response.headers["X-RateLimit-Reset"], str(int(START) + 60))
        self.assertEqual(response.json(), {"detail": "Too many attempts"})

    async def test_window_expiry_allows_requests_again(self):
        await self.get("/login")
        await self.get("/login")
        self.clock.return_value += 60

        (await self.get("/login")).assert_status(200)

    async def test_by_keys_are_counted_independently(self):
        for _ in range(2):
            await self.get("/users", headers={"x-user": "a"})

        (await self.get("/users", headers={"x-user": "a"})).assert_status(429)
        (await self.get("/users", headers={"x-user": "b"})).assert_status(200)

    async def test_all_limits_in_a_list_are_enforced(self):
        (await self.get("/layered")).assert_status(200)
        (await self.get("/layered")).assert_status(429)

        self.clock.return_value += 1
        (await self.get("/layered")).assert_status(200)
        self.clock.return_value += 1
        (await self.get("/layered")).assert_status(200)
        self.clock.return_value += 1
        (await self.get("/layered")).assert_status(429)

    async def test_unlimited_limits_are_skipped(self):
        for _ in range(5):
            response = await self.get("/open")
            response.assert_status(200)
        self.assertNotIn("X-RateLimit-Limit", response.headers)

    async def test_custom_response_callback_is_used(self):
        await self.get("/custom")

        response = await self.get("/custom")

        response.assert_status(429)
        self.assertEqual(response.json(), {"message": "slow down"})
        self.assertEqual(response.headers["Retry-After"], "60")

    async def test_async_custom_response_callback_is_awaited(self):
        await self.get("/custom-async")

        response = await self.get("/custom-async")

        response.assert_status(503)
        self.assertEqual(response.json(), {"message": "later"})

    async def test_unnamed_throttle_limits_by_client(self):
        (await self.get("/global")).assert_status(200)
        (await self.get("/global")).assert_status(429)

    async def test_unknown_limiter_raises(self):
        with self.assertRaisesRegex(LimiterNotDefinedException, r"Rate limiter \[missing\] is not defined."):
            await self.get("/missing")

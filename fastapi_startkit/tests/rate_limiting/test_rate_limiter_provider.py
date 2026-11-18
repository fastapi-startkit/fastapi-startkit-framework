import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.application import Application
from fastapi_startkit.cache import ArrayStoreConfig, CacheProvider, Repository
from fastapi_startkit.configuration import config
from fastapi_startkit.container.container import Container
from fastapi_startkit.facades import RateLimiter as RateLimiterFacade
from fastapi_startkit.rate_limiting import Limit, RateLimiter, RateLimiterProvider


@dataclass
class ArrayCacheConfig:
    default: str = "array"
    stores: dict = field(default_factory=lambda: {"array": ArrayStoreConfig(), "limits": ArrayStoreConfig()})


@dataclass
class LimitsStoreConfig:
    store: str = "limits"


class TestRateLimiterProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        os.environ.pop("RATE_LIMITER_STORE", None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        original_instance = Container._instance
        self.addCleanup(lambda: setattr(Container, "_instance", original_instance))

    def make_app(self, *providers):
        return Application(base_path=self.base_path, providers=list(providers))

    def test_binds_rate_limiter_and_merges_default_config(self):
        app = self.make_app(RateLimiterProvider)

        self.assertIsInstance(app.make("rate_limiter"), RateLimiter)
        self.assertIsNone(config("rate_limiter.store"))

    def test_falls_back_to_array_store_without_cache_provider(self):
        app = self.make_app(RateLimiterProvider)

        self.assertIsInstance(app.make("rate_limiter").cache, Repository)

    def test_uses_default_cache_store(self):
        app = self.make_app((CacheProvider, ArrayCacheConfig), RateLimiterProvider)

        self.assertIs(app.make("rate_limiter").cache, app.make("cache").store("array"))

    def test_uses_configured_cache_store(self):
        app = self.make_app((CacheProvider, ArrayCacheConfig), (RateLimiterProvider, LimitsStoreConfig))

        self.assertIs(app.make("rate_limiter").cache, app.make("cache").store("limits"))

    async def test_facade_proxies_to_the_bound_limiter(self):
        self.make_app(RateLimiterProvider)

        RateLimiterFacade.for_("login", lambda request: Limit.per_minute(5))

        self.assertEqual(await RateLimiterFacade.hit("key"), 1)
        self.assertEqual(RateLimiterFacade.limiter("login")(None), Limit.per_minute(5))

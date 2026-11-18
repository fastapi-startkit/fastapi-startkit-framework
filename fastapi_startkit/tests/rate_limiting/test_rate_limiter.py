from unittest import mock

import pytest

from fastapi_startkit.cache import ArrayStore, Repository
from fastapi_startkit.rate_limiting import Limit, LimiterNotDefinedException, RateLimiter, Unlimited


START = 1_000_000.0


@pytest.fixture
def frozen():
    with mock.patch("time.time", return_value=START) as clock:
        yield clock


@pytest.fixture
def limiter(frozen):
    return RateLimiter(lambda: Repository(ArrayStore()))


def advance(clock, seconds: int) -> None:
    clock.return_value += seconds


class TestLimit:
    def test_factories_set_attempts_and_decay(self):
        assert Limit.per_second(3) == Limit(3, 1)
        assert Limit.per_second(3, 5) == Limit(3, 5)
        assert Limit.per_minute(5) == Limit(5, 60)
        assert Limit.per_minute(5, 2) == Limit(5, 120)
        assert Limit.per_minutes(3, 10) == Limit(10, 180)
        assert Limit.per_hour(100) == Limit(100, 3600)
        assert Limit.per_hour(100, 2) == Limit(100, 7200)
        assert Limit.per_day(1000) == Limit(1000, 86400)
        assert Limit.per_day(1000, 7) == Limit(1000, 604800)

    def test_by_and_response_are_fluent(self):
        callback = lambda request, headers: None  # noqa: E731

        limit = Limit.per_minute(5).by(42).response(callback)

        assert limit.key == "42"
        assert limit.response_callback is callback

    def test_none_is_unlimited(self):
        assert isinstance(Limit.none(), Unlimited)


class TestRateLimiter:
    def test_named_limiters_are_registered_and_resolved(self, limiter):
        callback = lambda request: Limit.per_minute(5)  # noqa: E731

        assert limiter.for_("login", callback) is limiter
        assert limiter.limiter("login") is callback

    def test_unknown_limiter_raises(self, limiter):
        with pytest.raises(LimiterNotDefinedException, match=r"Rate limiter \[missing\] is not defined."):
            limiter.limiter("missing")

    def test_cache_is_resolved_once(self, frozen):
        calls = []
        limiter = RateLimiter(lambda: calls.append(1) or Repository(ArrayStore()))

        assert limiter.cache is limiter.cache
        assert calls == [1]

    async def test_hit_counts_attempts_until_limited(self, limiter):
        assert await limiter.hit("key") == 1
        assert await limiter.hit("key") == 2

        assert await limiter.attempts("key") == 2
        assert await limiter.remaining("key", 3) == 1
        assert await limiter.retries_left("key", 3) == 1
        assert not await limiter.too_many_attempts("key", 3)

        await limiter.hit("key")

        assert await limiter.too_many_attempts("key", 3)
        assert await limiter.remaining("key", 2) == 0

    async def test_decay_window_expiry_resets_attempts(self, frozen, limiter):
        await limiter.hit("key", 60)
        advance(frozen, 45)

        assert await limiter.attempts("key") == 1
        assert await limiter.available_in("key") == 15

        advance(frozen, 15)

        assert await limiter.attempts("key") == 0
        assert await limiter.available_in("key") == 0
        assert await limiter.hit("key", 60) == 1
        assert await limiter.available_in("key") == 60

    async def test_hits_in_window_keep_the_original_timer(self, frozen, limiter):
        await limiter.hit("key", 60)
        advance(frozen, 30)
        await limiter.hit("key", 60)

        assert await limiter.available_at("key") == START + 60

    async def test_keys_are_counted_independently(self, limiter):
        await limiter.hit("a")
        await limiter.hit("a")
        await limiter.hit("b")

        assert await limiter.attempts("a") == 2
        assert await limiter.attempts("b") == 1

    async def test_increment_and_decrement_by_amount(self, limiter):
        assert await limiter.increment("key", amount=5) == 5
        assert await limiter.decrement("key", amount=2) == 3

    async def test_attempt_runs_callback_until_limited(self, limiter):
        calls = []

        assert await limiter.attempt("key", 2, lambda: calls.append(1)) is True
        assert await limiter.attempt("key", 2, lambda: "sent") == "sent"
        assert await limiter.attempt("key", 2, lambda: calls.append(1)) is False
        assert calls == [1]

    async def test_attempt_treats_falsy_callback_results_as_success(self, limiter):
        assert await limiter.attempt("key", 2, lambda: False) is True
        assert await limiter.attempt("key", 2, lambda: 0) is True
        assert await limiter.attempt("key", 2, lambda: False) is False

    async def test_attempt_awaits_async_callbacks(self, limiter):
        async def send():
            return "async"

        assert await limiter.attempt("key", 1, send, decay_seconds=10) == "async"
        assert await limiter.available_in("key") == 10

    async def test_reset_attempts_keeps_the_timer(self, limiter):
        await limiter.hit("key")

        assert await limiter.reset_attempts("key")
        assert await limiter.attempts("key") == 0
        assert await limiter.available_in("key") == 60

    async def test_clear_removes_attempts_and_timer(self, limiter):
        await limiter.hit("key")

        await limiter.clear("key")

        assert await limiter.attempts("key") == 0
        assert await limiter.available_in("key") == 0

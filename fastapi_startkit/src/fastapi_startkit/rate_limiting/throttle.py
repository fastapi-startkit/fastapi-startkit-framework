import hashlib
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi_startkit.exceptions import HttpResponseException, ThrottleRequestsException

from .limit import Limit, Unlimited
from .limiter import RateLimiter

if TYPE_CHECKING:
    from fastapi import Request, Response


def limiter() -> RateLimiter:
    from fastapi_startkit.application import app

    return app().make("rate_limiter")


async def resolve_limits(rate_limiter: RateLimiter, name: str, request: "Request") -> list[Limit]:
    limits = rate_limiter.limiter(name)(request)
    if inspect.isawaitable(limits):
        limits = await limits
    return [limits] if isinstance(limits, Limit) else list(limits)


def signature(prefix: str, name: str, limit: Limit) -> str:
    return hashlib.md5(f"{prefix}{name}:{limit.decay_seconds}:{limit.key}".encode(), usedforsecurity=False).hexdigest()


async def limited(request: "Request", rate_limiter: RateLimiter, key: str, limit: Limit) -> Exception:
    retry_after = await rate_limiter.available_in(key)
    headers = {
        "X-RateLimit-Limit": str(limit.max_attempts),
        "X-RateLimit-Remaining": "0",
        "Retry-After": str(retry_after),
        "X-RateLimit-Reset": str(rate_limiter.now() + retry_after),
    }
    if limit.response_callback is None:
        return ThrottleRequestsException(headers=headers)

    response = limit.response_callback(request, headers)
    if inspect.isawaitable(response):
        response = await response
    return HttpResponseException(response)


def throttle(
    name: str | None = None, max_attempts: int = 60, decay_minutes: int = 1, prefix: str = ""
) -> Callable[["Request", "Response"], Awaitable[None]]:
    from fastapi import Request, Response

    async def dependency(request: Request, response: Response) -> None:
        rate_limiter = limiter()
        if name is None:
            host = request.client.host if request.client else ""
            limits = [Limit.per_minute(max_attempts, decay_minutes).by(host)]
        else:
            limits = await resolve_limits(rate_limiter, name, request)

        keyed = [(signature(prefix, name or "", limit), limit) for limit in limits if not isinstance(limit, Unlimited)]
        async with rate_limiter.locked(*(key for key, _ in keyed)):
            for key, limit in keyed:
                if await rate_limiter.too_many_attempts(key, limit.max_attempts):
                    raise await limited(request, rate_limiter, key, limit)

            for key, limit in keyed:
                hits = await rate_limiter.record(key, limit.decay_seconds)
                response.headers["X-RateLimit-Limit"] = str(limit.max_attempts)
                response.headers["X-RateLimit-Remaining"] = str(max(0, limit.max_attempts - hits))

    return dependency

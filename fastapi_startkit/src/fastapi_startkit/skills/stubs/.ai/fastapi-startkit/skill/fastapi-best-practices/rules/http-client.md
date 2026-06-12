# HTTP Client

Rules for making outbound HTTP requests in FastAPI Startkit applications.

## Rules

### Always set explicit timeouts

Set both `timeout` and `connect_timeout` on **every** request. Never rely on
the default (which may be infinite in some clients):

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "https://api.example.com/data",
        timeout=httpx.Timeout(timeout=10.0, connect=5.0),
    )
```

For a shared client (e.g. in a provider), set defaults at construction time:

```python
client = httpx.AsyncClient(
    timeout=httpx.Timeout(timeout=10.0, connect=5.0),
    base_url="https://api.example.com",
)
```

### Retry with exponential backoff for external APIs

Do not let transient failures propagate immediately. Use exponential backoff
with jitter on retryable status codes (429, 502, 503, 504):

```python
import asyncio
import httpx

RETRYABLE = {429, 502, 503, 504}

async def get_with_retry(url: str, max_retries: int = 3) -> httpx.Response:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        for attempt in range(max_retries + 1):
            try:
                response = await client.get(url)
                if response.status_code not in RETRYABLE:
                    return response
            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt == max_retries:
                    raise

            wait = 2 ** attempt  # 1 s, 2 s, 4 s …
            await asyncio.sleep(wait)

    raise RuntimeError("Max retries exceeded")
```

### Check response status explicitly

Always check the response status. Use `raise_for_status()` as a safe default
or inspect the code explicitly when you need to branch on specific errors:

```python
# Safe default — raises httpx.HTTPStatusError on 4xx / 5xx
response = await client.get(url)
response.raise_for_status()
data = response.json()

# Explicit branching
if response.status_code == 404:
    return None
if response.status_code == 429:
    raise RateLimitedError("External API rate limited")
response.raise_for_status()
```

Never silently ignore a failed status code.

### Use asyncio.gather() for concurrent independent requests

When multiple requests are independent of each other, run them concurrently
instead of sequentially:

```python
import asyncio
import httpx

async def fetch_all(urls: list[str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        responses = await asyncio.gather(
            *[client.get(url) for url in urls],
            return_exceptions=True,
        )
    results = []
    for r in responses:
        if isinstance(r, Exception):
            raise r
        r.raise_for_status()
        results.append(r.json())
    return results
```

### Mock HTTP clients in tests

Never hit real external APIs in tests. Use `respx` (for `httpx`) to intercept
and fake responses:

```python
import respx
import httpx

@respx.mock
async def test_fetch_user():
    respx.get("https://api.example.com/users/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Alice"})
    )
    result = await fetch_user(1)
    assert result["name"] == "Alice"
```

For stray-request protection (equivalent to Laravel's `preventStrayRequests`),
use `respx.mock(assert_all_mocked=True)` to raise on any unmocked call:

```python
@respx.mock(assert_all_mocked=True)
async def test_no_stray_requests():
    # Any unmocked httpx call will raise AssertionError
    ...
```

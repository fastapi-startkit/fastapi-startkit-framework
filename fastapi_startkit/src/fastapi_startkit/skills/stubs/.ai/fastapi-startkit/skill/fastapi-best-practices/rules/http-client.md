# HTTP Client

- Set explicit `timeout` and `connect_timeout` on every request — never rely on defaults.
- Retry on `{429, 502, 503, 504}` with exponential backoff; propagate on final attempt.
- Always call `response.raise_for_status()` or branch on `response.status_code` explicitly.
- Use `asyncio.gather()` for concurrent independent requests.
- Never hit real APIs in tests — mock with `respx`; use `assert_all_mocked=True` to catch strays.

```python
import httpx

async with httpx.AsyncClient(
    timeout=httpx.Timeout(timeout=10.0, connect=5.0),
    base_url="https://api.example.com",
) as client:
    response = await client.get("/data")
    response.raise_for_status()
    return response.json()
```

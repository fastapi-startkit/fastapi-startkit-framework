# 044. Slack log driver posts straight to chat.postMessage

Date: 2026-10-29

## Problem

`LogSlackDriver.send` resolved the configured channel name to an id by calling `channels.list` before every `chat.postMessage`. Slack retired `channels.list` in 2021. It now answers `{"ok": false, "error": "method_deprecated"}`, so `response.json()["channels"]` raised `KeyError: 'channels'` and every log sent to the `slack` channel crashed the caller.

`chat.postMessage` itself never needed the lookup: its `channel` argument accepts a channel name such as `#alerts` or a channel id such as `C0123456789`.

The driver also never looked at the `chat.postMessage` response, so a wrong token or a missing channel failed silently, and it sent the token as a form field instead of the `Authorization` header that Slack recommends.

## Alternatives

1. Replace `channels.list` with `conversations.list`. It needs the extra `channels:read` scope, is paginated (a workspace with more than one page of channels needs cursor handling), and adds a request to every log line for no gain.
2. Cache the id from `conversations.list`. Same scope and pagination cost, plus cache invalidation when a channel is renamed.
3. Drop the lookup and pass the configured channel to `chat.postMessage` as is.

## Decision

Option 3, approved by the user.

`post` sends JSON to `https://slack.com/api/chat.postMessage` with `Authorization: Bearer <token>`, the configured `channel` unchanged, the formatted `text`, and `username`/`icon_emoji` when they are set, with a 10 second timeout. It calls `raise_for_status()` and then checks the body: when `ok` is not true it raises `SlackApiError` with the Slack error code (`unknown_error` when the body has none), for example `Slack chat.postMessage failed for channel '#alerts': not_authed`. When the code is `channel_not_found` it raises `SlackChannelNotFound`, now a subclass of `SlackApiError`, so code that caught the old exception still catches the same situation. `post` is public for callers that want the strict behaviour.

The level methods go through `send`, which never raises. `ExceptionHandler.handle()` reports before it renders, and `StackChannel` calls its channels in a loop with no guard, so an exception from Slack would replace the original exception with a bare 500 and stop later channels such as `single` or `daily` from writing. `send` therefore catches `requests.RequestException` (connection errors, timeouts, HTTP errors, and `requests.JSONDecodeError` for a non-JSON body from a proxy), `ValueError` and `SlackApiError`, and writes `Slack log driver: <reason>` to stderr. stderr is used instead of `warnings.warn` because warnings are deduplicated per call site and can be turned into errors by filters.

`send` skips the request up front, with a stderr line, when `token` is not set, instead of sending `Bearer None` and paying a round trip for `not_authed`.

On a 429 `post` records `Retry-After` (default 30 seconds when the header is missing or not a number) and `send` skips messages until that time has passed, writing one stderr line per skipped message. Nothing sleeps, so a rate limit never blocks the caller, and messages logged during the window are dropped rather than queued. The window lives on the driver instance, which `Logger` keeps for the life of the process.

The config surface is unchanged: `driver`, `channel`, `emoji`, `username`, `token`, `level`. No setting existed only for the lookup, so none is removed. `channel` now also accepts a channel id.

Removed from the payload: `token` (moved to the header), `as_user` (classic apps only), `reply_broadcast` (only meaningful with `thread_ts`, which the driver never sends), and the explicit `unfurl_links`/`unfurl_media` flags. `find_channel` is removed.

## Implementation

- `logging/drivers/LogSlackDriver.py`: `SlackApiError`, `SlackChannelNotFound(SlackApiError)`, `send`, `post`, `retry_after` and `warn` as above, `find_channel` deleted.
- `tests/logging/test_logging.py`: the `find_channel` tests are replaced by tests that mock `requests.post`.
- `tests/exceptions/test_handler.py`: `handle()` still renders when Slack fails.
- `fastapi_startkit/CHANGELOG.md`: notes the removal of `find_channel` and the fail-soft behaviour.

User configuration:

```python
from fastapi_startkit.logging.config import SlackChannel

"slack": SlackChannel(
    channel="#alerts",
    token=env("SLACK_TOKEN"),
    level="error",
),
```

## Known limits and follow-ups

- `requests.post` is synchronous, so a log call from an async handler blocks the event loop for up to the 10 second timeout. This predates the change. A follow-up should move to `httpx.AsyncClient` or offload the request to a thread.
- Messages logged while rate limited are dropped, not retried.

## Validation

- `chat.postMessage` is called once with channel `#alerts`, the `Authorization: Bearer` header and the formatted message text; `channels.list` is never called.
- `post` raises `SlackApiError` for `{"ok": false, "error": "not_authed"}`, `SlackChannelNotFound` for `channel_not_found`, and `unknown_error` when there is no `error` key.
- The level methods write to stderr instead of raising for `ok: false`, `ConnectionError`, `Timeout`, an HTTP error status and a non-JSON body.
- A missing token sends no request.
- A 429 with `Retry-After: 5` skips the next message and sends again once 5 seconds have passed; an invalid `Retry-After` falls back to 30 seconds.
- A `StackChannel` with a failing Slack channel first still writes to the next channel.
- `ExceptionHandler.handle()` still returns the rendered response for the original exception when Slack fails.
- Unset `username`/`emoji` are not sent.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` (at least 80%), `ruff check`, `ruff format --check`.

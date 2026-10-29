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

`send` posts JSON to `https://slack.com/api/chat.postMessage` with `Authorization: Bearer <token>`, the configured `channel` unchanged, the formatted `text`, and `username`/`icon_emoji` when they are set. It calls `raise_for_status()` (non-2xx, for example a 429 rate limit, raises `requests.HTTPError`) and then checks the body: when `ok` is not true it raises `SlackApiError` with the Slack error code, for example `Slack chat.postMessage failed for channel '#alerts': not_authed`. When the code is `channel_not_found` it raises `SlackChannelNotFound`, now a subclass of `SlackApiError`, so code that caught the old exception still catches the same situation. Raising matches the other drivers, which let file and syslog errors propagate rather than swallowing them. Requests use a 10 second timeout so a slow Slack API cannot hang the caller.

The config surface is unchanged: `driver`, `channel`, `emoji`, `username`, `token`, `level`. No setting existed only for the lookup, so none is removed. `channel` now also accepts a channel id.

Removed from the payload: `token` (moved to the header), `as_user` (classic apps only), `reply_broadcast` (only meaningful with `thread_ts`, which the driver never sends), and the explicit `unfurl_links`/`unfurl_media` flags. `find_channel` is removed.

## Implementation

- `logging/drivers/LogSlackDriver.py`: `SlackApiError`, `SlackChannelNotFound(SlackApiError)`, `send` as above, `find_channel` deleted.
- `tests/logging/test_logging.py`: the `find_channel` tests are replaced by tests that mock `requests.post`.

User configuration:

```python
from fastapi_startkit.logging.config import SlackChannel

"slack": SlackChannel(
    channel="#alerts",
    token=env("SLACK_TOKEN"),
    level="error",
),
```

## Validation

- `chat.postMessage` is called once with channel `#alerts`, the `Authorization: Bearer` header and the formatted message text; `channels.list` is never called.
- `{"ok": false, "error": "not_authed"}` raises `SlackApiError`, not `KeyError`.
- `{"ok": false, "error": "channel_not_found"}` raises `SlackChannelNotFound`.
- An HTTP error status raises `requests.HTTPError`.
- Unset `username`/`emoji` are not sent.
- `uv run pytest --ignore=tests/masoniteorm/postgres --cov` (at least 80%), `ruff`, `basedpyright`.

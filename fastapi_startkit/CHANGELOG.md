# Changelog

## Unreleased

### Changed

- **Breaking:** the MCP `Server.router()` rejects requests without an `id` unless the method is a `notifications/*` notification. They answer 400 with `-32600` and are not dispatched, so an id-less `tools/call` no longer runs the tool. Send an `id` on every request.

- **Breaking:** an MCP tool whose `schema()` is a `FormRequest` now receives the validated instance in `handle`, not a JSON dump. Enums, dates, `model_fields_set` and request methods survive, and nothing is parsed twice. Read fields as attributes (`arguments.title`), or call `arguments.model_dump(mode="json", exclude_unset=True)` for the old dict. Tools without a `FormRequest` schema still receive the raw arguments. `Tool.handle` is typed `arguments: Any`.

- **Breaking:** `fastapi_startkit.mcp.JsonRpcRequest` is renamed to `MCPRequest`. Import `from fastapi_startkit.mcp import MCPRequest`.

- `fastapi_startkit.logging.Logger` is renamed to `Log`. Use `from fastapi_startkit.logging import Log`; the behaviour is unchanged.

### Deprecated

- `Logger` in `fastapi_startkit.logging` and `fastapi_startkit.logging.logger`. Importing it emits a `DeprecationWarning` and returns `Log`, so existing code, subclasses and `isinstance` checks keep working. It will be removed in a future major release.

### Fixed

- The MCP `Server.router()` answers malformed JSON with 400 and `-32700`, and a batch or a body without `method` with 400 and `-32600`, instead of 500.
- `PUT`, `PATCH`, `DELETE`, `HEAD` and `OPTIONS` on the MCP router answer 405 with `Allow: POST` after the dependencies passed to `include_router` run, so authentication covers every verb.
- The Slack log driver posts straight to `chat.postMessage` instead of resolving the channel through the retired `channels.list`, which made every Slack log raise `KeyError: 'channels'`. `channel` accepts a name such as `#alerts` or a channel id.
- Slack logging no longer raises from the level methods. Request errors, `ok: false` responses and non-JSON bodies are written to stderr, so the exception handler still renders the original exception and stack channels keep writing to later channels. A missing token skips the request, and a 429 pauses sending until `Retry-After` has passed.

### Removed

- `LogSlackDriver.find_channel`. It depended on `channels.list` and always raised `KeyError`. Use `LogSlackDriver.post` for a call that raises `SlackApiError` on failure.

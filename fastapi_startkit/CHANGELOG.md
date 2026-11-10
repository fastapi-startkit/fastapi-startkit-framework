# Changelog

## Unreleased

### Added

- `Tool.handle_request(request)` for MCP tools whose `schema()` is a `FormRequest`. `Tool.call` passes it the validated instance, so a tool that overrides it keeps enums, dates, `model_fields_set` and request methods without parsing the input again. The default dumps the request with `exclude_unset=True` and calls `handle`, so existing tools are unchanged.

### Changed

- `fastapi_startkit.logging.Logger` is renamed to `Log`. Use `from fastapi_startkit.logging import Log`; the behaviour is unchanged.

### Deprecated

- `Logger` in `fastapi_startkit.logging` and `fastapi_startkit.logging.logger`. Importing it emits a `DeprecationWarning` and returns `Log`, so existing code, subclasses and `isinstance` checks keep working. It will be removed in a future major release.

### Fixed

- The Slack log driver posts straight to `chat.postMessage` instead of resolving the channel through the retired `channels.list`, which made every Slack log raise `KeyError: 'channels'`. `channel` accepts a name such as `#alerts` or a channel id.
- Slack logging no longer raises from the level methods. Request errors, `ok: false` responses and non-JSON bodies are written to stderr, so the exception handler still renders the original exception and stack channels keep writing to later channels. A missing token skips the request, and a 429 pauses sending until `Retry-After` has passed.

### Removed

- `LogSlackDriver.find_channel`. It depended on `channels.list` and always raised `KeyError`. Use `LogSlackDriver.post` for a call that raises `SlackApiError` on failure.

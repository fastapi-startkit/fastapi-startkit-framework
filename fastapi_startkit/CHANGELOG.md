# Changelog

## Unreleased

### Fixed

- The Slack log driver posts straight to `chat.postMessage` instead of resolving the channel through the retired `channels.list`, which made every Slack log raise `KeyError: 'channels'`. `channel` accepts a name such as `#alerts` or a channel id.
- Slack logging no longer raises from the level methods. Request errors, `ok: false` responses and non-JSON bodies are written to stderr, so the exception handler still renders the original exception and stack channels keep writing to later channels. A missing token skips the request, and a 429 pauses sending until `Retry-After` has passed.

### Removed

- `LogSlackDriver.find_channel`. It depended on `channels.list` and always raised `KeyError`. Use `LogSlackDriver.post` for a call that raises `SlackApiError` on failure.

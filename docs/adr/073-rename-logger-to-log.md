# 073. Rename `Logger` to `Log`

Date: 2026-11-08

## Problem

`fastapi_startkit.logging` exports `Logger`, a class with static-style level methods (`Logger.info(...)`). Every other static-style service in the framework is named after its noun, as Laravel names its facades (`Config`, `Cache`, `Mail`), and Laravel calls this one `Log`. `Logger` also reads as an instance of the stdlib `logging.Logger`, which it is not, and it shadows that name for anyone who imports both.

Before renaming, the codebase was checked for a clash:

- `facades/` has no `Log` facade or `Log.pyi` stub, and no `Log` symbol is defined anywhere in `src/`.
- The container binds the default channel as `"logger"` and swaps the `Logger` class for that channel in `LogProvider.boot`. The string key names the channel, not the class, so it stays.
- `LoggerExceptionListener` type-hints its dependency with `Logger`.

So the rename needs no new facade and does not change the design.

## Alternatives

1. **Keep `Logger`.** No churn, but the name stays inconsistent with the rest of the API.
2. **Add a `Log` facade over the `"logger"` binding.** It would be a second, differently built entry point next to the class, with the same methods.
3. **Rename the class to `Log` and keep `Logger` as a deprecated alias.** One class, one canonical name, and existing imports keep working.

## Decision

Option 3.

- `logging/logger.py` defines `class Log`, unchanged apart from its name. The module keeps its file name, because `Log.logger_info` skips frames from `logger.py` to find the caller.
- `logging/logger.py` and `logging/__init__.py` define a module `__getattr__` that returns `Log` for `Logger` and emits `DeprecationWarning("Logger is deprecated; use Log instead")` with `stacklevel=2`. Anything else raises `AttributeError`. `Logger` is the same object as `Log`, so `isinstance`, `issubclass`, `patch.object` and the container swap keep working through either name.
- `__all__` lists `Log` and `LogProvider`; `Logger` is left out so `import *` does not warn.
- The exception handler, the `logging.Handler` bridge, `LogProvider` and `LoggerExceptionListener` use `Log`, as do the example apps and the docs.
- `pytest` turns the `Logger is deprecated` warning into an error, so any internal use of the old name fails the suite. Tests that exercise the alias catch it with `pytest.warns`.

`Logger` will be removed in a later major release.

## Validation

- `tests/logging/test_logging.py` checks that `Log` resolves the default channel and logs at every level, that `from fastapi_startkit.logging import Logger` and `from fastapi_startkit.logging.logger import Logger` warn, name `Log`, return `Log` and still log, that an unknown attribute raises `AttributeError`, and that `Logger` is absent from `__all__`.
- The full suite runs with the warning as an error.

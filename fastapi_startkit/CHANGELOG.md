# Changelog

## 0.48.0

### Breaking changes

The top-level `fastapi_startkit.providers` package has been removed. Its
contents moved into `foundation` and `support`, and there is **no**
backward-compatibility shim — consumers must update their imports:

| Old import | New import |
|---|---|
| `from fastapi_startkit.providers import Provider` | `from fastapi_startkit.support import Provider` |
| `from fastapi_startkit.providers.app_provider import ...` | `from fastapi_startkit.foundation.app_provider import ...` |
| `from fastapi_startkit.helpers.dataclass import ...` | `from fastapi_startkit.support.dataclass import ...` |

`fastapi_startkit.helpers.app` has been removed.

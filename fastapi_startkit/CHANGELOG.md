# Changelog

## Unreleased

### `serve` command defaults now come from `FastAPIConfig`

`ServeCommand` no longer restates defaults that `FastAPIConfig` already declares.
Every server setting resolves as **CLI flag > `fastapi` config > `FastAPIConfig` default**.

- **New `FastAPIConfig.app`** field (`"bootstrap.application:app"`), so the served
  entrypoint is configurable like every other setting. Add it to your
  `config/fastapi.py` if you want to override it:

  ```python
  app: str = "bootstrap.application:app"
  ```

- **Behaviour change:** an application that registers no `fastapi` config now gets
  `reload_excludes` (`["*.log", "tests/*", "node_modules/*"]`) passed to uvicorn when
  reload is on. Previously these were only forwarded when a config was registered, so
  such an app watched excluded paths. Set `reload_excludes = []` in your `fastapi`
  config to restore the old behaviour.

- A `fastapi` config key that is present but set to `None` now falls back to the
  `FastAPIConfig` default instead of being forwarded as `None`.

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

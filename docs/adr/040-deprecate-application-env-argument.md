# 040. Deprecate the `env` argument of `Application`

Date: 2026-10-25

## Problem

`Application(base_path=..., env="production")` hard-codes the deployment environment in source code. The same code base runs locally, in CI and in production, so the environment has to come from outside the code. The argument also outranks `APP_ENV`, so a hard-coded `env=` silently overrides the operator's choice. Only the pytest check runs before it.

The framework already has three external sources:

- the `APP_ENV` environment variable, set by the shell, the process manager or `.env`;
- the CLI `--env <name>` / `--env=<name>` option, which `Environment.resolve_environment_from_argument` turns into `APP_ENV` before Cleo parses arguments;
- pytest auto-detection (`PYTEST_CURRENT_TEST` gives `testing`, which loads `.env.testing`).

None of these depend on the constructor argument. Nothing in `src/`, `application/`, the installer stubs or the example bootstraps passes `env=`. Only the framework's own tests (`env="testing"`, which is redundant under pytest) and one `example/config-app` test pass it.

## Alternatives

1. Remove the argument now. That breaks every application that passes it, with no migration window, in a 0.x minor release.
2. Keep it and document `APP_ENV` as the preferred way. Hard-coded values keep winning over `APP_ENV`, which is the problem.
3. Deprecate it now and remove it in 1.0.

## Decision

Option 3. Passing a non-`None` `env` to `Application.__init__` emits a `DeprecationWarning` with `stacklevel=2`, so the warning points at the user's `Application(...)` call. It says the argument will be removed in 1.0 and to use `APP_ENV` or `--env`. Resolution order and behaviour stay the same until removal.

`Application.set_environment()` is unchanged. It switches the environment of a running application, together with `load_environment()`, and does not put a deployment environment in the bootstrap file.

## Implementation

- `fastapi_startkit/src/fastapi_startkit/application.py`: warn when `env is not None`.
- Framework tests stop passing `env="testing"`, since pytest detection already selects `testing`.
- `fastapi_startkit/pyproject.toml` turns this deprecation into an error under pytest (`filterwarnings`), so the framework test suite cannot add new `env=` calls.
- `example/config-app/tests/test_config_app.py` selects environments through `APP_ENV` (`patch.dict`).

## Validation

- `tests/core/test_application_env_deprecation.py`:
  - `env=` warns, and the warning's filename is the caller's file;
  - `env=` still selects the environment;
  - no warning without `env`;
  - `APP_ENV`, `--env <name>` and `--env=<name>` select the environment without a warning, and the `--env` tokens are removed from `sys.argv`;
  - pytest detection gives `testing`.
- The warning tests fail before the change.
- The full suite passes with the error filter, and coverage stays above 80%.
- `example/config-app` tests pass.

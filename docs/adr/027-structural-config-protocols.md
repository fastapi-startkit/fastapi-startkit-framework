# 027. Structural config protocols for application and database settings

- Date: 2026-10-21 (amended 2026-11-08: migrations settings and `ensure_config`)
- Status: Accepted

## Problem

Application config classes had to subclass a framework base to be accepted, for example `class DatabaseConfig(BaseDatabaseConfig)`. Most providers did not need this: Redis, Storage, Vite, Logging, FastAPI, AI and Broadcasting call `resolve_config`, which converts any dataclass, pydantic model or dict with `Dataclass.to_dict` and merges it over the provider defaults. Two places were nominal:

1. `DatabaseProvider.register` used a `DatabaseConfig` instance as-is but rebuilt any other dataclass as `DatabaseConfig(**fields(source))`. A plain dataclass with an extra field failed with `TypeError: DatabaseConfig.__init__() got an unexpected keyword argument`, and the user's object was replaced by a copy. `DatabaseManager` rejected anything that was not a `DatabaseConfig`, and `ShellCommand` was annotated with it.
2. `Application` bound `TConfig` to `AppConfig`, so type checkers rejected `Application(config=MyPlainConfig)` although runtime only instantiates the class and reads `debug` with `getattr`.

The first version of `DatabaseSettings` described only `default` and `connections`, but the framework also reads migrations settings: `DBMigrateCommand`, `MigrateStatusCommand`, `MigrateRollbackCommand`, `MigrateResetCommand`, `MigrateFreshCommand` and `MigrateRefreshCommand` all call `config.get("database.migrations").get("directory")`. A plain config without `migrations` booted and then failed inside the commands, and `example/inertia-pingcrm-app` declared `"path"` instead of `"directory"`, so its directory resolved to `None`. Wrong values such as a `default` that names no connection also surfaced only at first query.

Audit of other migration-related settings: `migrations.table` is declared by `DatabaseConfig` but not read (`MigrationModel.__table__` and `Migrator` hardcode `"migrations"`). Seeder directories are `--directory`/`--seed-directory` option defaults (`databases/seeders`), not config.

## Alternatives

- **Keep the copy and drop unknown fields.** Silently loses data and still replaces the user's object.
- **Duck typing with `hasattr` only.** Works at runtime but gives type checkers nothing to check against.
- **Resolve `env()` without the `Config` metaclass**, for example with a `__post_init__` helper, so plain dataclasses gain everything the base offers. Broader change; left for a follow-up.
- **`runtime_checkable` Protocols describing the attributes the framework reads.** Chosen.

For migrations:

- **Nested `MigrationSettings` Protocol with `table`/`directory` attributes.** Every existing config, including the framework default, stores `migrations` as a `dict`, and the commands read it with `.get`; an attribute Protocol would reject all of them.
- **`TypedDict` for the keys.** A `dict[str, str]` dataclass field is not assignable to a `TypedDict` property, so plain configs would fail type checking.
- **Optional `migrations`, filled from the base default.** Protocols cannot express optional members for `isinstance`, and the previous nominal design always provided `migrations` through the base class, so requiring it restores that guarantee. Chosen: required, `Mapping[str, str]`.

For validation:

- **A method on the Protocols.** Plain dataclasses would have to implement it, which defeats structural typing.
- **`ensure_config(settings: DatabaseSettings)` with one function per Protocol.** Callers would need a different name per namespace, and dispatching on `isinstance` cannot name missing attributes for an object that matches neither Protocol.
- **`ensure_config(settings, namespace)` with a validator per namespace.** Chosen. The namespace is the dotted config key the settings are merged under, so errors name keys exactly as `Config.get` does (`database.migrations.directory`), and the same function covers `"app"`.

## Decision

- `fastapi_startkit.masoniteorm.config.database.DatabaseSettings` is a `runtime_checkable` Protocol with read-only `default: str`, `connections: Mapping[str, DBConfig]` and `migrations: Mapping[str, str]`. Read-only properties let dataclass fields typed `dict[str, DBConfig]` and `dict[str, str]` satisfy it.
- `ensure_database_settings(owner, source)` returns the source when it satisfies `DatabaseSettings` and otherwise raises `TypeError("<owner> requires database settings; missing attributes: <names>")`. `DatabaseManager` uses it to narrow its argument.
- `fastapi_startkit.support.config.ensure_config(settings, namespace) -> None` validates and raises `ConfigurationError(key, problem)`, a subclass of the existing `InvalidConfigurationSetup` exposing `.key`. `support/config.py` becomes the `support/config/` package (`base.py` keeps `Config`, `validation.py` holds the helper), and the package exports `Config`, `ConfigurationError` and `ensure_config`. Rules, checked in order with the first failure raised:
  - `"database"`: `default` is a non-empty string; `connections` is a mapping whose values are `DBConfig`; `default` is one of its keys; `migrations` is a mapping with non-empty string `table` and `directory`.
  - `"app"`: `name`, `env` and `timezone` are non-empty strings and `debug` is a bool.
  - Any other namespace raises `ValueError`.
  `DBConfig` is imported inside the database validator so `support` neither depends on the `database` extra nor forms an import cycle with `masoniteorm`, which imports `Config` from `support.config`.
- `DatabaseProvider.register` is the single place database settings enter the framework, so it calls `ensure_config(source, "database")` before building the manager and fails fast at boot. It uses the configured object as-is, falling back to `DatabaseConfig()` when none is given. The dotted config entry is built with `resolve_config(DatabaseConfig)`, so extra user fields are kept. `ensure_config` is not called for `"app"` at boot in this change; applications can call it themselves.
- `example/agents` declares `migrations`, and `example/inertia-pingcrm-app` uses `directory` instead of `path`.
- `DatabaseManager` and `ShellCommand` are typed against `DatabaseSettings`, and `DatabaseManager` validates with `ensure_database_settings`.
- `fastapi_startkit.application.AppSettings` is a `runtime_checkable` Protocol with `name`, `env`, `debug` and `timezone`, and `TConfig` is bound to it.
- `DatabaseConfig`, `AppConfig` and the other `Config` subclasses are unchanged and remain the defaults and optional bases. Subclasses keep constructor `env()` resolution and class-level default access through the `Config` metaclass, and a subclass instance is used as-is as before.

## Usage

```python
from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DBConfig, PostgresConfig


@dataclass
class DatabaseConfig:
    default: str = env("DB_CONNECTION", "postgres")
    connections: dict[str, DBConfig] = field(
        default_factory=lambda: {"postgres": PostgresConfig(host=env("DB_HOST", "localhost"))}
    )
    migrations: dict[str, str] = field(
        default_factory=lambda: {"table": "migrations", "directory": "databases/migrations"}
    )
```

```python
from fastapi_startkit.support.config import ConfigurationError, ensure_config

try:
    ensure_config(settings, "database")
except ConfigurationError as error:
    print(error.key)
```

Limitation of plain dataclasses: `env()` returns a `dataclasses.field`, so it works as a field default and as an argument to framework classes such as `PostgresConfig`, but `MyPlainConfig(default=env("X"))` stores the unresolved `Field`. Class-level default access such as `MyPlainConfig.connections` also needs the `Config` base. Subclass `Config` (or the framework base) when either is needed.

## Validation

- `tests/core/test_structural_config.py`: a plain app config and a plain database config with an extra field boot, the database settings object is the same instance, `database.migrations` is the configured mapping, a config without `migrations` fails `isinstance(..., DatabaseSettings)` and boot, the framework `DatabaseConfig` and every `example/*/config/database.py` satisfy `DatabaseSettings`, a `DatabaseConfig` subclass keeps `env()` kwargs and class-level defaults, a wrong shape raises `ConfigurationError` naming the missing key, and basedpyright type-checks a copy of the file with no errors (it reports `TConfig` errors when the bound is `AppConfig`).
- `tests/support/test_config_validation.py`: valid database and app settings, missing and empty `default`, `default` not in `connections`, non-mapping `connections`, non-`DBConfig` connection, missing or non-mapping `migrations`, missing `table`/`directory`, empty `directory`, non-bool `debug`, empty `name`, unknown namespace.
- `example/agents/config/database.py` drops the base class.
- Follow-ups: installer stubs still generate `class X(BaseX)`, the documentation site, re-exporting `DatabaseSettings`/`AppSettings` from package `__init__` modules, `env()` resolution for plain dataclasses, reading `migrations.table` in `MigrationModel`/`Migrator`, and calling `ensure_config(config, "app")` from `Application`.

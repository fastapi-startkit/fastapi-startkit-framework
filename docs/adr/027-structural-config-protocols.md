# 027. Structural config protocols for application and database settings

- Date: 2026-10-21 (amended 2026-11-08: migrations settings; the database-only settings check generalised as `ensure_config`)
- Status: Accepted

## Problem

Application config classes had to subclass a framework base to be accepted, for example `class DatabaseConfig(BaseDatabaseConfig)`. Most providers did not need this: Redis, Storage, Vite, Logging, FastAPI, AI and Broadcasting call `resolve_config`, which converts any dataclass, pydantic model or dict with `Dataclass.to_dict` and merges it over the provider defaults. Two places were nominal:

1. `DatabaseProvider.register` used a `DatabaseConfig` instance as-is but rebuilt any other dataclass as `DatabaseConfig(**fields(source))`. A plain dataclass with an extra field failed with `TypeError: DatabaseConfig.__init__() got an unexpected keyword argument`, and the user's object was replaced by a copy. `DatabaseManager` rejected anything that was not a `DatabaseConfig`, and `ShellCommand` was annotated with it.
2. `Application` bound `TConfig` to `AppConfig`, so type checkers rejected `Application(config=MyPlainConfig)` although runtime only instantiates the class and reads `debug` with `getattr`.

The first version of `DatabaseSettings` described only `default` and `connections`, but the framework also reads migrations settings: `DBMigrateCommand`, `MigrateStatusCommand`, `MigrateRollbackCommand`, `MigrateResetCommand`, `MigrateFreshCommand` and `MigrateRefreshCommand` all call `config.get("database.migrations").get("directory")`. A plain config without `migrations` booted and then failed inside the commands, and `example/inertia-pingcrm-app` declared `"path"` instead of `"directory"`, so its directory resolved to `None`.

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

For checking a settings object against a Protocol:

- **One helper per Protocol** (the first version had a database-only helper with a hardcoded attribute tuple). Every new Protocol would need a copy, and the tuple drifts from the Protocol.
- **A method on the Protocols.** Plain dataclasses would have to implement it, which defeats structural typing.
- **A key-by-key validator per config namespace** (non-empty `default`, `default` in `connections`, migrations keys). Rejected: it duplicates the Protocols as hand-written rules and changes provider behaviour; value checks stay where the values are used.
- **One generic `ensure_config(owner, source, protocol)`.** Chosen. It keeps the database helper's semantics, takes the Protocol as an argument, lists the Protocol's own members when reporting what is missing, and returns the source typed as the Protocol.

## Decision

- `fastapi_startkit.masoniteorm.config.database.DatabaseSettings` is a `runtime_checkable` Protocol with read-only `default: str`, `connections: Mapping[str, DBConfig]` and `migrations: Mapping[str, str]`. Read-only properties let dataclass fields typed `dict[str, DBConfig]` and `dict[str, str]` satisfy it.
- `fastapi_startkit.support.config.ensure_config[T](owner: str, source: object, protocol: type[T]) -> T` returns `source` when `isinstance(source, protocol)` and otherwise raises `TypeError("<owner> requires <Protocol>; missing attributes: <names>")`. Names are the Protocol's members (`__protocol_attrs__`) in declaration order, filtered to those `source` lacks. The Protocol must be `runtime_checkable`. basedpyright infers the return type as the Protocol. It replaces the database-only helper from the first version of this PR, which was never released, so no alias is kept. `support/config.py` becomes the `support/config/` package (`base.py` keeps `Config`, `ensure.py` holds the helper), and the package exports `Config` and `ensure_config`. It imports nothing from `masoniteorm`, so there is no import cycle and no dependency on the `database` extra.
- `DatabaseProvider.register` calls `ensure_config("DatabaseProvider", source or DatabaseConfig(), DatabaseSettings)` and still raises `TypeError` for connections that are not `DBConfig`. It uses the configured object as-is, falling back to `DatabaseConfig()` when none is given. The dotted config entry is built with `resolve_config(DatabaseConfig)`, so extra user fields are kept. `DatabaseManager` calls `ensure_config("DatabaseManager", config, DatabaseSettings)`.
- `example/agents` declares `migrations`, and `example/inertia-pingcrm-app` uses `directory` instead of `path`.
- `DatabaseManager` and `ShellCommand` are typed against `DatabaseSettings`.
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
from fastapi_startkit.application import AppSettings
from fastapi_startkit.masoniteorm.config.database import DatabaseSettings
from fastapi_startkit.support.config import ensure_config

database = ensure_config("MyService", settings, DatabaseSettings)
app_settings = ensure_config("MyService", config, AppSettings)
```

Limitation of plain dataclasses: `env()` returns a `dataclasses.field`, so it works as a field default and as an argument to framework classes such as `PostgresConfig`, but `MyPlainConfig(default=env("X"))` stores the unresolved `Field`. Class-level default access such as `MyPlainConfig.connections` also needs the `Config` base. Subclass `Config` (or the framework base) when either is needed.

## Validation

- `tests/core/test_structural_config.py`: a plain app config and a plain database config with an extra field boot, the database settings object is the same instance, `database.migrations` is the configured mapping, a config without `migrations` fails `isinstance(..., DatabaseSettings)` and boot, the framework `DatabaseConfig` and every `example/*/config/database.py` satisfy `DatabaseSettings`, a `DatabaseConfig` subclass keeps `env()` kwargs and class-level defaults, a wrong shape raises `TypeError` naming the owner, the Protocol and the missing attributes, `ensure_config` returns valid `DatabaseSettings` and `AppSettings` sources typed as the Protocol (`assert_type`) and lists every missing member for invalid ones, and basedpyright type-checks a copy of the file with no errors (it reports `TConfig` errors when the bound is `AppConfig`).
- `example/agents/config/database.py` drops the base class.
- Follow-ups: installer stubs still generate `class X(BaseX)`, the documentation site, re-exporting `DatabaseSettings`/`AppSettings` from package `__init__` modules, `env()` resolution for plain dataclasses, and reading `migrations.table` in `MigrationModel`/`Migrator`.

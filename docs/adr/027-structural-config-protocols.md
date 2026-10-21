# 027. Structural config protocols for application and database settings

- Date: 2026-10-21
- Status: Accepted

## Problem

Application config classes had to subclass a framework base to be accepted, for example `class DatabaseConfig(BaseDatabaseConfig)`. Most providers did not need this: Redis, Storage, Vite, Logging, FastAPI, AI and Broadcasting call `resolve_config`, which converts any dataclass, pydantic model or dict with `Dataclass.to_dict` and merges it over the provider defaults. Two places were nominal:

1. `DatabaseProvider.register` used a `DatabaseConfig` instance as-is but rebuilt any other dataclass as `DatabaseConfig(**fields(source))`. A plain dataclass with an extra field failed with `TypeError: DatabaseConfig.__init__() got an unexpected keyword argument`, and the user's object was replaced by a copy. `DatabaseManager` rejected anything that was not a `DatabaseConfig`, and `ShellCommand` was annotated with it.
2. `Application` bound `TConfig` to `AppConfig`, so type checkers rejected `Application(config=MyPlainConfig)` although runtime only instantiates the class and reads `debug` with `getattr`.

## Alternatives

- **Keep the copy and drop unknown fields.** Silently loses data and still replaces the user's object.
- **Duck typing with `hasattr` only.** Works at runtime but gives type checkers nothing to check against.
- **Resolve `env()` without the `Config` metaclass**, for example with a `__post_init__` helper, so plain dataclasses gain everything the base offers. Broader change; left for a follow-up.
- **`runtime_checkable` Protocols describing the attributes the framework reads.** Chosen.

## Decision

- `fastapi_startkit.masoniteorm.config.database.DatabaseSettings` is a `runtime_checkable` Protocol with read-only `default: str` and `connections: Mapping[str, DBConfig]`. Read-only properties let a dataclass field typed `dict[str, DBConfig]` satisfy it.
- `ensure_database_settings(owner, source)` returns the source when it satisfies `DatabaseSettings` and otherwise raises `TypeError("<owner> requires database settings; missing attributes: <names>")`.
- `DatabaseProvider` uses the configured object as-is, falling back to `DatabaseConfig()` when none is given. It still rejects connections that are not `DBConfig`. The dotted config entry is built with `resolve_config(DatabaseConfig)`, so `migrations` and any other base default stays available as `database.migrations` while extra user fields are kept.
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
```

Limitation of plain dataclasses: `env()` returns a `dataclasses.field`, so it works as a field default and as an argument to framework classes such as `PostgresConfig`, but `MyPlainConfig(default=env("X"))` stores the unresolved `Field`. Class-level default access such as `MyPlainConfig.connections` also needs the `Config` base. Subclass `Config` (or the framework base) when either is needed.

## Validation

- `tests/core/test_structural_config.py`: a plain app config and a plain database config with an extra field boot, the database settings object is the same instance, `database.migrations` keeps its default, a `DatabaseConfig` subclass keeps `env()` kwargs and class-level defaults, a wrong shape raises `TypeError` naming the missing attributes, and basedpyright type-checks a copy of the file with no errors (it reports `TConfig` errors when the bound is `AppConfig`).
- `example/agents/config/database.py` drops the base class.
- Follow-ups: installer stubs still generate `class X(BaseX)`, the documentation site, re-exporting `DatabaseSettings`/`AppSettings` from package `__init__` modules, and `env()` resolution for plain dataclasses.

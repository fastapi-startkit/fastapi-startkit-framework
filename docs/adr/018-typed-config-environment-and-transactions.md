# ADR 018: Typed configuration, deferred env() defaults, config-owned database URLs and transaction management

Date: 2026-10-15
Status: Accepted

## Problem

- `env()` read the environment when it was called. Used as a dataclass default it ran at module import, before `.env` and `.env.{APP_ENV}` were loaded, so settings were declared as `field(default_factory=lambda: env(...))`. `env(key, "")` inferred integers and booleans instead of returning a string, so string settings such as passwords were wrapped in `str(...)` and lost leading zeroes.
- Class attribute access on a settings dataclass (`DatabaseConfig.default`) failed for factory-backed fields, because dataclasses remove those class attributes.
- Database connections took either dictionaries or the `SQLiteConfig`/`MySQLConfig`/`PostgresConfig` dataclasses. The factory, connections and schema inspection branched on both shapes, and URL building and SQLite engine options lived in `ConnectionFactory` as driver `if` chains.
- A dictionary or other invalid connection entry was only rejected lazily, when the connection was first resolved.
- `Connection` mixed SQL execution with the transaction lifecycle and the after-commit bookkeeping of ADR 006 (a private frame bag in a nested dictionary with a root counter for ordering).
- Redis options and connections were dictionaries of eager environment reads.
- Some ORM modules imported from the `fastapi_startkit.masoniteorm` package itself, which risks import cycles when the package's `__init__` imports them.

## Alternatives

- `env()` returning a zero-argument callable, or a callable `Field` subclass: needs a private subclass relying on `Field.__init__` internals that differ between Python versions, and still needs `field()` for collections.
- A custom `lazy()` helper for collection defaults: duplicates `dataclasses.field(default_factory=...)`.
- Resolving deferred values on first instance attribute access (`Config.__getattribute__` with caching): keeps unresolved `Field` objects inside instances, needed plain dataclasses instead of Pydantic ones for that reason, and makes instance state depend on access order.
- Requiring `value(env(...))` for every constructor argument: makes `env()` read differently in declarations and calls.
- Normalising dictionaries into driver dataclasses at the factory boundary: keeps two input shapes and a conversion layer.
- A `connectors/` package with one connector per driver: a second class hierarchy mirroring the config classes one-to-one, plus `match` statements pairing configs with connectors and wrappers.
- Validating connection configs in `Connection` and `ConnectionFactory.make`: late and duplicated.
- Moving the transaction context manager into `TransactionsManager`: makes the record registry depend on connection ownership and the task-scoped ContextVar.

## Decision

### Environment

`env(name, default, cast)` returns `dataclasses.field(default_factory=read)`. `read` looks up the variable when the dataclass is constructed and converts it with `into()`. An explicit default decides the type, including `""`, which now returns a string; an omitted default (a private sentinel) or `None` keeps numeric and boolean inference; `cast=False` returns the raw string. Overloads give `env()` the type of the resolved value, so `port: int = env("DB_PORT", 5432)` type-checks without a wrapper.

`value(item: T) -> T` returns the default factory result of a `Field` and every other item unchanged; it does not call plain callables. It is the resolver for call sites outside `Config` constructors, for example dictionary entries. The `environment` package exports `env`, `into` and `value` through `__all__`.

### Config base class

`fastapi_startkit.support.config.Config` (exported from `fastapi_startkit.configuration`) uses the metaclass `_ConfigMeta`:

- `__call__` passes every positional and keyword argument through `value()` before the dataclass `__init__`, so `SQLiteConfig(database=env("DB_DATABASE", ...))` stores the value, not the `Field`.
- `__getattr__` resolves a dataclass field's default factory on class access, without caching, and raises `AttributeError` for unknown or required fields.

Instances resolve all defaults at construction. Framework settings (`AppConfig`, database, Redis, storage disks, logging channels, FastAPI, broadcasting, AI, Vite) inherit `Config` and declare scalars with bare `env(...)`; collections use `field(default_factory=...)` and construct nested `Config` objects with bare `env(...)` arguments. `value(env(...))` remains only where the target is not a `Config` constructor.

### Database configuration

Connection settings are typed only. `DBConfig` is a runtime-checkable protocol with `driver`, `url`, `database`, `echo`, `options`, `schema`, `build_url()` and `engine_options()`. Each driver config owns its URL: the explicit `url` when set, otherwise the driver URL, with MySQL and PostgreSQL falling back to ports 3306 and 5432. `SQLiteConfig.engine_options()` returns `check_same_thread=False` with `StaticPool`; the others return nothing.

`ConnectionFactory.create_engine()` is the single engine path: it checks the driver against `CONNECTIONS`, applies `echo`, and uses `NullPool` under testing or the config's engine options otherwise. `create_connection(driver, config)` resolves the wrapper class from `CONNECTIONS` and rejects unsupported drivers (`DriverNotFound`) and a driver argument that differs from `config.driver` (`ValueError`). `build_url()` checks the driver only when no explicit URL is set.

`DatabaseConfig` inherits `Config`; `connections` is `dict[str, DBConfig]` and defaults to `{"sqlite": SQLiteConfig(database=env("DB_DATABASE", "databases/sqlite.db"))}`. `DatabaseProvider.register` accepts a `DatabaseConfig` or another settings dataclass (copied field by field), raises `TypeError` for anything else, and raises `TypeError` naming the connection for any entry that is not a `DBConfig`. The typed config goes to `DatabaseManager`; a dictionary copy goes to the configuration service.

### Transactions

Mirroring Laravel:

- `connections/transactions.py`: `TransactionRecord` (parent, callbacks, `descends_from`, async `execute_callbacks` awaiting awaitable results) and `TransactionsManager`, a pure registry keyed by SQLAlchemy connection and transaction (`begin`, `commit`, `rollback`, `add_callback`, `current`, `forget`). A committed savepoint appends its callbacks to its parent, so registration order holds across nesting without a counter; a root commit returns its record for execution after the connection is released; rollback discards the record and its descendants.
- `connections/manages_transactions.py`: the `ManagesTransactions` mixin inherited by `Connection` owns `transactions`, `transaction()`, `begin_transaction()` (returns the started transaction), `commit_transaction()`/`rollback()` (optional target, innermost by default), `after_commit()` and connection release. `Transaction` is a thin async context manager that stores its owner and transaction and delegates to them.

The behaviour of ADR 006 and the public transaction API are unchanged. Rollback callbacks and the closure form `transaction(callback, attempts)` are out of scope.

### Redis

`RedisOptions` and `RedisConnectionConfig` are `Config` dataclasses. `RedisConfig.options` defaults to `RedisOptions()`; `connections` to `{"default": RedisConnectionConfig(), "cache": RedisConnectionConfig(database=env("REDIS_CACHE_DB", 1))}`. `RedisOptions.prefix` uses `REDIS_PREFIX` when set and otherwise the slugged `APP_NAME`. `RedisProvider` still converts settings with `Dataclass.to_dict`, so `RedisManager` receives dictionaries.

### Imports

Modules inside `masoniteorm` import from their defining modules (for example `masoniteorm.connections.manager.DatabaseManager`) rather than from the `fastapi_startkit.masoniteorm` package, which re-exports `DBConfig` and `DatabaseConfig` for applications.

## Implementation

- `environment/environment.py`: `env()` with overloads and the nested `read`; `value()`; `into()` with the `_UNSET` sentinel. `fastapi/commands/serve_command.py` parses the `reload` option explicitly instead of using the old value parser.
- `support/config.py`: `Config` and `_ConfigMeta`; `configuration/__init__.py` re-exports `Config`. The configuration service helper and the `Config` facade keep their names.
- `masoniteorm/config/config.py` and `config/database.py`: `DBConfig`, driver configs with `build_url()`/`engine_options()`, `DatabaseConfig`. The `connectors/` package does not exist.
- `masoniteorm/connections/factory.py`, `manager.py`, `connection.py` (`Connection(ManagesTransactions)`; `Transaction` and `AfterCommitCallback` stay importable from it), `transactions.py`, `manages_transactions.py`. `schema/schema.py` reads `connection.config.database` and `.schema`; `ShellCommand` reads the typed `DatabaseConfig`.
- `masoniteorm/providers/DatabaseProvider.py`: input and connection validation. `migrations/Migrator.py` imports `DatabaseManager` from its module.
- `redis/config.py`, `storage/config/`, `logging/config/`, `config/app.py`, `fastapi/config/fastapi.py`, `broadcasting/config.py`, `ai/config/`, `vite/config/vite.py`: settings on `Config` with bare `env()`; the example apps follow the same form.

## Validation

- `tests/environment/test_env.py` and `test_lazy_env.py`: no read at declaration, reads after environment loading, empty-string and leading-zero strings, omitted and `None` defaults, boolean and numeric casting, `cast=False`, `value()` on fields and plain items.
- `tests/core/test_base_config.py` and `tests/support/test_config_env_arguments.py`: class access to defaults, required and unknown attributes, overrides, collection isolation, positional and keyword `env()` constructor arguments, and `DatabaseConfig()` building the SQLite URL from `DB_DATABASE`.
- `tests/masoniteorm/config/test_db_url.py`, `test_manager.py`, `test_database_config.py`: config-built URLs, explicit URL overrides, default ports, SQLite engine options, `NullPool` under testing, unsupported and mismatched drivers, and the provider's `TypeError` for dictionary connections.
- `tests/masoniteorm/connections/test_transactions.py`, `test_after_commit.py`, `tests/masoniteorm/sqlite/builder/test_sqlite_transaction.py`: record and manager units, and the ADR 006 after-commit behaviour unchanged.
- `tests/redis/test_config.py`: dataclass attributes, environment overrides and prefix fallback.
- `uv run pytest --ignore=tests/masoniteorm/postgres`, `basedpyright` and `ruff check` from `fastapi_startkit/`.

# 035. Config subclasses work without `@dataclass`

Date: 2026-10-23

## Problem

`env()` returns a `dataclasses.Field` with a `default_factory`, so it only becomes a value when the class is processed by `@dataclass`. `Config` relies on every subclass being decorated. A plain subclass is never processed:

```python
class DatabaseConfig(Config):
    default: str = env("DB_CONNECTION", "sqlite")

DatabaseConfig().default
DatabaseConfig.default
```

Both lookups fall back to the class attribute, which is the raw `Field`. The value is never read from the environment or cast.

## Alternatives

1. Make `env()` return a descriptor instead of a `Field`. This breaks dataclass configs, which need a `Field` to get a per-instance `default_factory`, and changes `value()` and the `_ConfigMeta` lookups.
2. Apply `dataclass` lazily, the first time a class is instantiated or subclassed. Instances work, but class-level access (`DatabaseConfig.default`) on a class that was never instantiated still returns the `Field`, and the lazy path needs a lock, MRO walks and rules for which classes to process.
3. Apply `dataclass` to every subclass when it is defined, in `Config.__init_subclass__`. Class-level access works immediately. The risk is a subclass that is also decorated with `@dataclass`: it is processed twice, and the second pass reads the defaults through `getattr`, which returns resolved `env()` values instead of `Field` objects, freezing them at import time and rejecting mutable `default_factory` results.

## Decision

Option 3, in `support/config.py`:

- `Config.__init_subclass__` records the class namespace, with copies of its `Field` objects, and applies `dataclass(eq=False)` to the new class. It uses `frozen=True` when the nearest dataclass ancestor is frozen, because dataclasses forbid a non-frozen child of a frozen parent. A class that already has its own `__dataclass_fields__` (the class `@dataclass(slots=True)` rebuilds) is skipped.
- An explicit `@dataclass` re-processes the class harmlessly. `dataclass` starts every pass by setting `__dataclass_params__` on the class, so `_ConfigMeta.__setattr__` uses that write to restore the recorded namespace: attributes added by the automatic pass are deleted and fresh copies of the original `Field` objects are put back. The decorator then processes the class as if it ran alone, so its options (`eq`, `frozen`, `kw_only`, ...) apply and `env()` values stay live. The namespace is restored only once, on the first pass after definition.
- `Config` is decorated with `typing.dataclass_transform(eq_default=False, field_specifiers=(field, Field))`, so type checkers treat undecorated subclasses as dataclasses.
- `Config` itself is not a dataclass. An empty dataclass base would make every `@dataclass(frozen=True)` subclass fail with `cannot inherit frozen dataclass from a non-frozen one`.
- `eq=False` keeps the identity equality and hashing undecorated subclasses had before.
- `_ConfigMeta` keeps resolving `env()` arguments in `__call__` and resolving `default_factory` fields on class-level access in `__getattr__`. The lazy processing, its lock and its class-selection rules are removed.

Every undecorated subclass now follows dataclass rules at definition time: a bare annotation (`name: str`) is a required argument, a plain mutable default (`opts: dict = {}`) raises `ValueError`, and an inherited custom `__init__` is replaced by the generated one, exactly as with `@dataclass`. Use `ClassVar` for shared class state and `field(default_factory=...)` for mutable defaults.

## Validation

- Static access: `AppConfig.name` on an undecorated class that was never instantiated returns the resolved value, for both undecorated and decorated classes, and a monkeypatched variable is read on the next access. `Config.get("app.name")` returns the value for a registered instance or class, and reflects an overridden variable.
- An undecorated subclass is a dataclass at definition: fallback value, variable value, `int`/`bool` casting, keyword arguments, and the environment being read on every instantiation.
- Explicit `@dataclass`: fields are collected once, `env()` stays live on the class and on instances, `default_factory` containers are per instance, and `frozen`, `kw_only` and `eq` from the decorator apply.
- Inheritance: undecorated parent and child, a `@dataclass` child of an undecorated parent, and undecorated children of a frozen parent are frozen.
- `Config` is not a dataclass, and undecorated instances stay hashable.
- Storage: an undecorated `MemoryDiskConfig` in an undecorated storage config resolves through `StorageManager`.
- Full suite without Postgres and basedpyright pass.

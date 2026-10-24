# 035. Config subclasses work without `@dataclass`

Date: 2026-10-23

## Problem

`env()` returns a `dataclasses.Field` with a `default_factory`, so it only becomes a value when the class is processed by `@dataclass`. `Config` relies on every subclass being decorated. A plain subclass is never processed:

```python
class DatabaseConfig(Config):
    default: str = env("DB_CONNECTION", "sqlite")

DatabaseConfig().default
```

`Config` has no `__init__` of its own, so the instance has no attribute and the lookup falls back to the class attribute, which is the raw `Field`. The value is never read from the environment or cast.

## Alternatives

1. Make `env()` return a descriptor instead of a `Field`. This breaks dataclass configs, which need a `Field` to get a per-instance `default_factory`, and changes `value()` and the `_ConfigMeta` lookups.
2. Apply `dataclass` eagerly in `__init_subclass__`. Subclasses that are also decorated with `@dataclass` would be processed twice; the first pass deletes the `Field` class attributes, so the second pass turns every `env()` field into a required argument.
3. Apply `dataclass` lazily in `_ConfigMeta.__call__`, the first time an unprocessed class is instantiated. Decorators have already run by then, so decorated classes are untouched.

## Decision

Option 3. Before instantiating, `_ConfigMeta.__call__` walks the class MRO from the base down and applies `dataclass` to every `Config` class whose own `__dict__` has no `__dataclass_fields__`. Undecorated parents are processed first so their `env()` fields are inherited as fields. Decorated classes, `Config.get` dotted access and `Configuration.set` (which uses `dataclasses.fields`) behave as before. Values are cast by the existing `env()` rules: the default's type decides the cast, so `env("DB_PORT", 5432)` returns an `int`.

Class-level access (`DatabaseConfig.default`) on an undecorated class that has never been instantiated still returns the `Field`, because intercepting class attribute reads would also intercept `@dataclass`'s own reads of the class. Instantiating once, or decorating the class, gives resolved class-level access.

## Validation

- Tests for an undecorated subclass: the fallback value without the variable, the variable's value when set, `int` and `bool` casting, explicit keyword arguments, an undecorated parent with an undecorated child, and a decorated class that is still processed exactly once.
- The reported repro prints `'sqlite'`.
- Full suite without Postgres passes with the coverage threshold.

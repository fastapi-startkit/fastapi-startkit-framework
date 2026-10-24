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
2. Apply `dataclass` eagerly to every subclass in `__init_subclass__`. A subclass that is also decorated is then processed twice. The first pass deletes the `default_factory` class attributes, so the second pass reads them with `getattr`, which reaches `_ConfigMeta.__getattr__` and gets the resolved value. Every `env()` field is frozen to its value at import time, and any `field(default_factory=...)` returning a dict or list fails with `ValueError: mutable default ... use default_factory`. This was checked on Python 3.15.
3. Apply `dataclass` lazily, the first time an unprocessed class is instantiated or subclassed. By then the class's own decorator, if any, has already run, so no class is processed twice.

## Decision

Option 3, in `support/config.py`:

- `_ConfigMeta.__call__` processes every unprocessed class in the instantiated class's MRO, base first, before building the instance.
- `Config.__init_subclass__` processes the new class's unprocessed ancestors before its own decorator runs. A `@dataclass` child of an undecorated parent therefore inherits the parent's fields; otherwise the parent would be processed after the child and its `Field` class attributes deleted from under the child.
- A class is processed only when it is a `Config` subclass, has no `__dataclass_fields__` in its own `__dict__`, and its own `__dict__` holds a `dataclasses.Field` (an `env()` or `field()` default). Every other class is left exactly as before, so plain mutable defaults (`opts: dict = {}`), bare annotations (`name: str`) and undecorated children of frozen dataclasses keep working, and `Config` itself, which holds no `Field`, is never a dataclass.
- A skipped class in the middle of the hierarchy does not block inheritance. Its processed ancestor's `__init__` and `__dataclass_fields__` are inherited, so instantiating it resolves the ancestor's `env()` fields, and a processed descendant collects the ancestor's fields through it. The skipped class's own annotations are not dataclass fields; its plain class attributes are still read through the class.
- Automatic processing uses `dataclass(eq=False)`, so undecorated subclasses keep the identity equality and hashing they had before, and `frozen=True` when the nearest dataclass ancestor is frozen, because dataclasses forbid a non-frozen child of a frozen parent. Classes the user decorates follow normal `@dataclass` rules.
- Processing runs under a module lock with a re-check inside it, so concurrent first instantiations process a class once.

Values are cast by the existing `env()` rules: the default's type decides the cast, so `env("DB_PORT", 5432)` returns an `int`. Decorated classes, `Config.get` dotted access and `Configuration.set` behave as before.

A single class body that mixes `env()` fields with a plain mutable default (`opts: dict = {}`) is processed and raises the usual dataclass `ValueError`; before this change such a class returned raw `Field`s, so it never worked. Use `field(default_factory=dict)` there.

Class-level access (`DatabaseConfig.default`) on an undecorated leaf class that has been neither instantiated nor subclassed still returns the `Field`. No hook runs between class creation and a following decorator, so processing the leaf earlier would bring back the double processing of option 2.

## Validation

- Tests for an undecorated subclass: the fallback value without the variable, the variable's value when set, `int` and `bool` casting, explicit keyword arguments, and the environment being read again on every instantiation.
- Inheritance: an undecorated parent with an undecorated child, and a `@dataclass` child of an undecorated parent that keeps the parent's fields.
- `Config` is never a dataclass, undecorated subclass instances stay hashable, a decorated class is processed exactly once, and eight threads instantiating a new class at the same time process it once.
- Classes without a `Field` are untouched: an undecorated child of a frozen dataclass, a plain `dict` default and a bare annotation behave as before. An `env()` child of a frozen parent is processed as frozen. In a mixed hierarchy (`env()` base, plain middle class with a bare annotation and a dict default, `env()` leaf) only the base and leaf are processed, and the middle class still resolves the base's fields.
- The reported repro prints `'sqlite'`.
- Full suite without Postgres passes with the coverage threshold.

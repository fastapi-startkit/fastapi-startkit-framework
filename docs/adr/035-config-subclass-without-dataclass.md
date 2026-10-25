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
- A class is processed when it is a `Config` subclass, has no `__dataclass_fields__` in its own `__dict__`, its `__init__` does not come from a custom, non-dataclass class in its MRO, and either its own `__dict__` holds a `dataclasses.Field` (an `env()` or `field()` default) or it declares field annotations that all have hashable defaults (`driver: str = "memory"`). Every other class is left exactly as on main, so bare annotations (`name: str`), plain mutable or unhashable defaults (`registry: dict = {}`, an object holding a `Lock`), custom `__init__` methods and undecorated children of frozen dataclasses with no annotations of their own keep working, and `Config` itself, which declares nothing, is never a dataclass. Own annotations are read with `annotationlib.get_annotations(format=FORWARDREF)` on Python 3.14+ and from `__dict__["__annotations__"]` before that.
- `ClassVar` and `InitVar` annotations are not counted as fields, in both real and string form (`from __future__ import annotations`). A string is resolved against the class's module the way `@dataclass` resolves it, so `"ClassVar[...]"` and `"typing.ClassVar[...]"` count only when the name resolves to `typing.ClassVar`; an unresolved string is treated as a field, which leaves a class with a mutable default unprocessed instead of failing.
- In a class that holds a `Field`, a plain default whose type is exactly `dict`, `list` or `set` becomes `field(default_factory=default.copy)`, the case `@dataclass` itself rejects. The copy is shallow: each instance gets its own container, but the objects inside it are shared. No other default is copied.
- A skipped class in the middle of the hierarchy does not block inheritance. Its processed ancestor's `__init__` and `__dataclass_fields__` are inherited, so instantiating it resolves the ancestor's `env()` fields, and a processed descendant collects the ancestor's fields through it. The skipped class's own annotations are not dataclass fields; its plain class attributes are still read through the class.
- Automatic processing uses `dataclass(eq=False)`, so undecorated subclasses keep the identity equality and hashing they had before, and `frozen=True` when the nearest dataclass ancestor is frozen, because dataclasses forbid a non-frozen child of a frozen parent. Classes the user decorates follow normal `@dataclass` rules.
- Processing runs under a module lock with a re-check inside it, so concurrent first instantiations process a class once.

Values are cast by the existing `env()` rules: the default's type decides the cast, so `env("DB_PORT", 5432)` returns an `int`. Decorated classes, `Config.get` dotted access and `Configuration.set` behave as before.

A `@dataclass(frozen=True)` child of an undecorated `env()` parent raises `TypeError: cannot inherit frozen dataclass from a non-frozen one` at class definition, because `__init_subclass__` processes the parent as non-frozen before the child's decorator runs and cannot see it. Put `@dataclass(frozen=True)` on the parent instead.

Class-level access (`DatabaseConfig.default`) on an undecorated leaf class that has been neither instantiated nor subclassed still returns the `Field`. No hook runs between class creation and a following decorator, so processing the leaf earlier would bring back the double processing of option 2.

Once a plain-default class has been processed, its defaults are baked into the generated `__init__`. A class-level override made after the first instantiation or subclassing (`MemoryDiskConfig.driver = "redis"`, or `monkeypatch.setattr` on the class) changes what the class attribute returns but is ignored by new instances, which still get `"memory"`. This is standard `@dataclass` behaviour; pass the value as a keyword argument instead (`MemoryDiskConfig(driver="redis")`).

For a class that holds a `Field` and also has a plain container default, the copied default has three edges. None of them is a regression: on main these classes were never processed, so their `env()` fields returned raw `Field` objects and the feature did not work for them at all:

- `registry: dict = {}` becomes a `default_factory`, so class-level `Cls.registry` returns a new dict on every access and writes through the class are lost. Keep shared state in a `ClassVar`.
- The copy is shallow, so nested containers (`{"tags": []}`) are shared between instances. Use `field(default_factory=...)` when nested values must be independent.
- Only exact `dict`, `list` and `set` are copied. A subclass default such as `OrderedDict()` is passed to `@dataclass` unchanged and raises `ValueError: mutable default ... use default_factory`. Use `field(default_factory=OrderedDict)`.

## Bug fix: plain-default configs without `@dataclass`

The first version processed only classes whose own body held a `Field`. A config with only plain defaults, such as a custom storage disk, was skipped once `@dataclass` was removed:

```python
class MemoryDiskConfig(Config):
    driver: str = "memory"
    prefix: str = ""

MemoryDiskConfig(prefix="app/")  # TypeError: MemoryDiskConfig() takes no arguments
```

`MemoryDiskConfig()` also stayed a plain object, so `Configuration.set` and `Dataclass.to_dict` left it unconverted and `StorageManager.get_config_options(...).get("driver")` failed. The rule now also processes classes whose annotations all have defaults, and a body that mixes `env()` fields with `opts: dict = {}` no longer raises the `ValueError` the first version raised (on main its `env()` fields returned raw `Field` objects).

The first version of this fix processed any class whose annotations all had defaults and deep-copied unhashable defaults. That changed classes that work on main:

- `registry: ClassVar[dict] = {}` was counted as a field and raised `ValueError`/`TypeError`, also next to `env()` fields and under string annotations.
- A shared class-level `registry: dict = {}` was copied for every instance, so mutations through the class were lost.
- A class with its own `__init__` and `opts: dict = {}` got a generated `__init__` that replaced it.
- An unhashable object that cannot be copied, such as one holding a `threading.Lock`, failed in `deepcopy`.

The plain-default branch is now limited to hashable defaults in classes without a custom `__init__`, `ClassVar`/`InitVar` are skipped, and only exact `dict`/`list`/`set` defaults in `Field`-bearing classes are copied, shallowly. A class with a custom `__init__` is left as on main even when it uses `env()`: its `env()` attributes stay raw `Field` objects unless its `__init__` sets them, so such a class should either set them itself or use `@dataclass`.

## Validation

- Tests for an undecorated subclass: the fallback value without the variable, the variable's value when set, `int` and `bool` casting, explicit keyword arguments, and the environment being read again on every instantiation.
- Inheritance: an undecorated parent with an undecorated child, and a `@dataclass` child of an undecorated parent that keeps the parent's fields.
- `Config` is never a dataclass, undecorated subclass instances stay hashable, a decorated class is processed exactly once, and eight threads instantiating a new class at the same time process it once.
- An undecorated child of a frozen dataclass with no annotations of its own and a bare annotation are untouched. A plain `dict` default alone is left unprocessed and shared through the class; next to `env()` fields it is copied shallowly per instance. `ClassVar` defaults next to plain and `env()` fields, string `ClassVar`/`InitVar` annotations, a module using `from __future__ import annotations` and an unresolvable string annotation are covered, on Python 3.15, 3.13 and 3.12. Classes with a custom `__init__` (own or inherited) and classes with an unhashable object default holding a `Lock` are left as on main. A plain-default class without `env()` accepts keyword arguments, converts with `Dataclass.to_dict` and keeps class-level access.
- Storage custom driver: an undecorated `MemoryDiskConfig` in an undecorated `StorageConfig` resolves through `StorageManager.disk("memory")` and `disk()`, and reads `env()` values. An `env()` child of a frozen parent is processed as frozen. In a mixed hierarchy (`env()` base, plain middle class with a bare annotation and a dict default, `env()` leaf) only the base and leaf are processed, and the middle class still resolves the base's fields.
- The reported repro prints `'sqlite'`.
- Full suite without Postgres passes with the coverage threshold.

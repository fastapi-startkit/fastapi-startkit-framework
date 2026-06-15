"""Fluent JSON assertions for HTTP tests.

Provides :class:`AssertableJson`, a chainable wrapper around a decoded JSON
body (``dict``/``list``).

Example::

    response.assert_json(lambda json: (
        json.where("id", 1)
            .where("name", "Bedu")
            .where("active", lambda v: v is True)
            .has("profile", lambda profile: (
                profile.where("email", "a@b.com").etc()
            ))
            .etc()
    ))

Every ``where``/``has`` call records an interaction with the touched key.
When an assertion scope closes, :meth:`AssertableJson._verify` asserts that
every property of an object was interacted with — unless :meth:`etc` was
called to acknowledge the remaining keys. This catches unexpected or extra
keys in responses.
"""

from __future__ import annotations

from typing import Any, Callable, Union

# A sentinel distinguishing "argument not provided" from an explicit ``None``.
_MISSING = object()

# Mapping of friendly type names to the Python types that satisfy them.
# ``bool`` is intentionally excluded from the numeric types because in Python
# ``bool`` is a subclass of ``int`` and JSON keeps the two concepts distinct.
_JSON_TYPES: dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "double": lambda v: isinstance(v, float),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


class AssertableJson:
    """A chainable, scope-aware assertion helper for decoded JSON bodies."""

    def __init__(self, data: Any, path: str = "") -> None:
        self._data = data
        self._path = path
        self._interacted: set[str] = set()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _full(self, key: Any) -> str:
        """Return the absolute dot-path to ``key`` for error messages."""
        return f"{self._path}.{key}" if self._path else str(key)

    @staticmethod
    def _step(node: Any, seg: str) -> tuple[bool, Any]:
        """Descend one segment into a dict key or a list index."""
        if isinstance(node, dict) and seg in node:
            return True, node[seg]
        if isinstance(node, list) and seg.lstrip("-").isdigit():
            index = int(seg)
            if -len(node) <= index < len(node):
                return True, node[index]
        return False, None

    def _exists(self, key: Any) -> bool:
        node = self._data
        for seg in str(key).split("."):
            found, node = self._step(node, seg)
            if not found:
                return False
        return True

    def _get(self, key: Any) -> Any:
        """Resolve a (possibly dotted) ``key`` or raise with the full path."""
        node = self._data
        for seg in str(key).split("."):
            found, node = self._step(node, seg)
            assert found, f"Property [{self._full(key)}] does not exist."
        return node

    def _record(self, key: Any) -> None:
        """Track that the top-level segment of ``key`` was interacted with."""
        self._interacted.add(str(key).split(".")[0])

    # ------------------------------------------------------------------ #
    # Matching — where family
    # ------------------------------------------------------------------ #
    def where(self, key: str, expected: Union[Any, Callable[[Any], bool]]) -> "AssertableJson":
        """Assert that ``key`` matches ``expected``.

        ``expected`` may be a literal value, or a callable predicate that
        receives the actual value and returns a truthy result.
        """
        self._record(key)
        actual = self._get(key)
        if callable(expected):
            assert expected(actual), f"Property [{self._full(key)}] was unexpected value [{actual!r}]."
        else:
            assert actual == expected, (
                f"Property [{self._full(key)}] does not match. Expected [{expected!r}], got [{actual!r}]."
            )
        return self

    def where_not(self, key: str, expected: Union[Any, Callable[[Any], bool]]) -> "AssertableJson":
        """Assert that ``key`` does NOT match ``expected`` (value or predicate)."""
        self._record(key)
        actual = self._get(key)
        if callable(expected):
            assert not expected(actual), (
                f"Property [{self._full(key)}] was not expected to pass the "
                f"given predicate but did (value [{actual!r}])."
            )
        else:
            assert actual != expected, f"Property [{self._full(key)}] was not expected to equal [{expected!r}] but did."
        return self

    def where_all(self, bindings: dict) -> "AssertableJson":
        """Assert each ``{key: expected}`` pair via :meth:`where`."""
        for key, expected in bindings.items():
            self.where(key, expected)
        return self

    def where_all_type(self, bindings: dict) -> "AssertableJson":
        """Assert each ``{key: type}`` pair via :meth:`where_type`."""
        for key, expected in bindings.items():
            self.where_type(key, expected)
        return self

    def where_type(self, key: str, expected: Union[str, list[str]]) -> "AssertableJson":
        """Assert that ``key`` is one of the given JSON type name(s).

        Accepts a single name (``"string"``), a pipe form (``"string|null"``)
        or a list (``["string", "null"]``). Supported names: string, integer,
        double, number, boolean, array, object, null.
        """
        self._record(key)
        actual = self._get(key)
        if isinstance(expected, str):
            names = expected.split("|")
        else:
            names = list(expected)
        for name in names:
            if name not in _JSON_TYPES:
                raise ValueError(f"Unknown JSON type [{name}] for [{self._full(key)}].")
        assert any(_JSON_TYPES[name](actual) for name in names), (
            f"Property [{self._full(key)}] is not of expected type [{'|'.join(names)}]; got value [{actual!r}]."
        )
        return self

    # ------------------------------------------------------------------ #
    # Presence — has family
    # ------------------------------------------------------------------ #
    def has(
        self,
        key: str,
        length: Any = _MISSING,
        callback: Callable[["AssertableJson"], Any] = _MISSING,
    ) -> "AssertableJson":
        """Assert that ``key`` exists, optionally its length and/or a scope.

        Supports the shorthands:

        * ``has("key")`` — just assert presence.
        * ``has("key", 3)`` — assert it is a sized collection of length 3.
        * ``has("key", callback)`` — scope into ``key`` and run nested asserts.
        * ``has("key", 3, callback)`` — both length and a nested scope.
        """
        self._record(key)
        value = self._get(key)

        # ``has("key", callback)`` shorthand: length slot holds the callback.
        if callable(length):
            callback = length
            length = _MISSING

        if length is not _MISSING:
            assert isinstance(value, (list, dict, str)), f"Property [{self._full(key)}] is not countable."
            assert len(value) == length, (
                f"Property [{self._full(key)}] does not have the expected size. "
                f"Expected [{length}], got [{len(value)}]."
            )

        if callback is not _MISSING:
            child = AssertableJson(value, self._full(key))
            callback(child)
            child._verify()

        return self

    def has_all(self, *keys: str) -> "AssertableJson":
        """Assert that every key in ``keys`` exists. Accepts a list or varargs."""
        for key in self._flatten(keys):
            assert self._exists(key), f"Property [{self._full(key)}] does not exist."
            self._record(key)
        return self

    def has_any(self, *keys: str) -> "AssertableJson":
        """Assert that at least one key in ``keys`` exists."""
        keys = self._flatten(keys)
        for key in keys:
            self._record(key)
        assert any(self._exists(key) for key in keys), (
            f"None of the expected properties [{', '.join(map(self._full, keys))}] exist."
        )
        return self

    def missing(self, key: str) -> "AssertableJson":
        """Assert that ``key`` is absent from the current scope."""
        assert not self._exists(key), f"Property [{self._full(key)}] was expected to be missing but exists."
        return self

    def missing_all(self, *keys: str) -> "AssertableJson":
        """Assert that none of ``keys`` exist."""
        for key in self._flatten(keys):
            self.missing(key)
        return self

    def count(self, key: str, length: int) -> "AssertableJson":
        """Assert that the collection at ``key`` has exactly ``length`` items."""
        return self.has(key, length)

    @staticmethod
    def _flatten(keys: tuple) -> tuple:
        """Allow both ``has_all("a", "b")`` and ``has_all(["a", "b"])``."""
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            return tuple(keys[0])
        return keys

    # ------------------------------------------------------------------ #
    # Traversal — first / each
    # ------------------------------------------------------------------ #
    def first(self, callback: Callable[["AssertableJson"], Any]) -> "AssertableJson":
        """Scope into the first child element and run ``callback`` against it."""
        assert self._data, f"Cannot scope into the first element of empty [{self._path or 'root'}]."
        if isinstance(self._data, list):
            key, value = 0, self._data[0]
        else:
            key, value = next(iter(self._data.items()))
        child = AssertableJson(value, self._full(key))
        callback(child)
        child._verify()
        self._record(key)
        return self

    def each(self, callback: Callable[["AssertableJson"], Any]) -> "AssertableJson":
        """Run ``callback`` against every child element in its own scope."""
        if isinstance(self._data, list):
            items = list(enumerate(self._data))
        elif isinstance(self._data, dict):
            items = list(self._data.items())
        else:
            raise AssertionError(f"Property [{self._path or 'root'}] is not iterable for each().")
        for key, value in items:
            child = AssertableJson(value, self._full(key))
            callback(child)
            child._verify()
            self._record(key)
        return self

    # ------------------------------------------------------------------ #
    # Interaction control
    # ------------------------------------------------------------------ #
    def etc(self) -> "AssertableJson":
        """Acknowledge any remaining, un-asserted keys in this scope."""
        if isinstance(self._data, dict):
            self._interacted.update(self._data.keys())
        return self

    def _verify(self) -> None:
        """Assert every object property was interacted with (or ``etc``'d)."""
        if isinstance(self._data, dict):
            extra = set(self._data.keys()) - self._interacted
            assert not extra, (
                f"Unexpected properties were found at [{self._path or 'root'}]: "
                f"{sorted(extra)}. Interact with them or call .etc()."
            )

    # ------------------------------------------------------------------ #
    # Phase-2 / TODO — explicit stubs.
    # ------------------------------------------------------------------ #
    def where_contains(self, key: str, expected: Any) -> "AssertableJson":  # pragma: no cover
        """TODO(phase-2): assert the collection at ``key`` contains ``expected``."""
        raise NotImplementedError("where_contains is planned for phase 2.")

    def count_between(self, key: str, minimum: int, maximum: int) -> "AssertableJson":  # pragma: no cover
        """TODO(phase-2): assert the size of ``key`` is within [min, max]."""
        raise NotImplementedError("count_between is planned for phase 2.")


def assert_json_structure(structure: Any, data: Any, path: str = "root") -> None:
    """Assert that ``data`` contains the keys described by ``structure``.

    ``structure`` may be:

    * a list of leaf key names, e.g. ``["name", "sport"]`` — each must exist
      on the object ``data``;
    * a dict mapping a key to a nested structure, e.g.
      ``{"teams": ["name", "sport"]}``;
    * a ``"*"`` key whose value is applied to every element of a list, e.g.
      ``{"teams": {"*": ["name", "sport"]}}``.

    A leaf may map to ``None`` in dict form to assert presence only.
    """
    if isinstance(structure, list):
        for value in structure:
            if isinstance(value, (list, dict)):
                assert_json_structure(value, data, path)
            else:
                assert isinstance(data, dict) and value in data, f"Missing key [{value}] at [{path}]."
        return

    if isinstance(structure, dict):
        for key, value in structure.items():
            if key == "*":
                assert isinstance(data, list), f"Expected a list at [{path}]."
                for index, item in enumerate(data):
                    assert_json_structure(value, item, f"{path}.{index}")
            else:
                assert isinstance(data, dict) and key in data, f"Missing key [{key}] at [{path}]."
                if value is not None:
                    assert_json_structure(value, data[key], f"{path}.{key}")
        return

    raise TypeError(f"Invalid structure node at [{path}]: {structure!r}")

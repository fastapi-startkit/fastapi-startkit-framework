"""Fluent URI parser and builder — fastapi_startkit.support.uri.

Usage::

    from fastapi_startkit.support.uri import Uri

    url = (
        Uri.of("https://example.com/api/users?page=1&sort=asc")
        .with_path("/api/posts")
        .add_query("page", 2)
        .remove_query("sort")
        .with_fragment("results")
        .get()
    )
    # "https://example.com/api/posts?page=2#results"
"""

from __future__ import annotations

from typing import Any
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse


class Uriable:
    """Fluent URI builder returned by :meth:`Uri.of`.

    Every mutating method returns a *new* ``Uriable`` so the original is
    not modified (value-object semantics).
    """

    def __init__(
        self,
        parsed: ParseResult,
        query: dict[str, list[str]] | None = None,
    ) -> None:
        self._parsed = parsed
        # Maintain query params as ``dict[str, list[str]]`` — same format as
        # ``urllib.parse.parse_qs``.  We keep this separately so round-tripping
        # through urlencode/parse_qs stays consistent.
        self._query: dict[str, list[str]] = (
            query if query is not None else parse_qs(parsed.query, keep_blank_values=True)
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_netloc(self, hostname: str | None = None, port: int | None = ...) -> str:  # type: ignore[assignment]
        """Reconstruct the ``netloc`` component preserving auth information."""
        hostname = hostname if hostname is not None else (self._parsed.hostname or "")
        port = self._parsed.port if port is ... else port

        netloc = hostname
        if port:
            netloc = f"{netloc}:{port}"

        username = self._parsed.username
        password = self._parsed.password
        if username:
            auth = f"{username}:{password}@" if password else f"{username}@"
            netloc = auth + netloc

        return netloc

    def _rebuild(self, **overrides: Any) -> Uriable:
        """Return a new ``Uriable`` with selective component overrides."""
        new_query: dict[str, list[str]] = overrides.pop("query", self._query)

        new_parsed = ParseResult(
            scheme=overrides.get("scheme", self._parsed.scheme),
            netloc=overrides.get("netloc", self._parsed.netloc),
            path=overrides.get("path", self._parsed.path),
            params=overrides.get("params", self._parsed.params),
            query=urlencode(new_query, doseq=True),
            fragment=overrides.get("fragment", self._parsed.fragment),
        )
        return Uriable(new_parsed, new_query)

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------

    def scheme(self) -> str:
        """Return the URI scheme (e.g. ``'https'``)."""
        return self._parsed.scheme

    def host(self) -> str:
        """Return the hostname without port (e.g. ``'example.com'``)."""
        return self._parsed.hostname or ""

    def port(self) -> int | None:
        """Return the port number, or ``None`` if not explicitly set."""
        return self._parsed.port

    def path(self) -> str:
        """Return the path component (e.g. ``'/api/users'``)."""
        return self._parsed.path

    def query(self) -> dict[str, list[str]]:
        """Return all query parameters as ``{key: [value, ...]}``."""
        return dict(self._query)

    def query_param(self, key: str, default: Any = None) -> str | None:
        """Return the *first* value for ``key``, or *default* if absent."""
        values = self._query.get(key)
        return values[0] if values else default

    def fragment(self) -> str:
        """Return the fragment (hash) component, without the leading ``#``."""
        return self._parsed.fragment

    def get(self) -> str:
        """Return the fully assembled URI string."""
        return urlunparse(self._parsed)

    # ------------------------------------------------------------------
    # Fluent mutators — each returns a new Uriable
    # ------------------------------------------------------------------

    def with_scheme(self, scheme: str) -> Uriable:
        """Replace the scheme (e.g. ``'http'`` → ``'https'``)."""
        return self._rebuild(scheme=scheme)

    def with_host(self, host: str) -> Uriable:
        """Replace the hostname, preserving port and authentication info."""
        netloc = self._build_netloc(hostname=host)
        return self._rebuild(netloc=netloc)

    def with_port(self, port: int | None) -> Uriable:
        """Set (or clear) the port, preserving hostname and auth."""
        netloc = self._build_netloc(port=port)
        return self._rebuild(netloc=netloc)

    def with_path(self, path: str) -> Uriable:
        """Replace the entire path component."""
        return self._rebuild(path=path)

    def append_path(self, segment: str) -> Uriable:
        """Append *segment* to the current path, handling trailing slashes."""
        base = self._parsed.path.rstrip("/")
        segment = segment.lstrip("/")
        return self._rebuild(path=f"{base}/{segment}")

    def with_query(self, params: dict[str, Any]) -> Uriable:
        """Replace *all* query parameters with the supplied mapping."""
        new_query: dict[str, list[str]] = {}
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                new_query[key] = [str(v) for v in value]
            else:
                new_query[key] = [str(value)]
        return self._rebuild(query=new_query)

    def add_query(self, key: str, value: Any) -> Uriable:
        """Add or replace a single query parameter."""
        new_query = dict(self._query)
        new_query[key] = [str(value)]
        return self._rebuild(query=new_query)

    def remove_query(self, key: str) -> Uriable:
        """Remove a query parameter (no-op if absent)."""
        new_query = {k: v for k, v in self._query.items() if k != key}
        return self._rebuild(query=new_query)

    def with_fragment(self, fragment: str) -> Uriable:
        """Set the fragment (hash), without the leading ``#``."""
        return self._rebuild(fragment=fragment)

    def without_fragment(self) -> Uriable:
        """Remove the fragment component."""
        return self._rebuild(fragment="")

    def without_query(self) -> Uriable:
        """Remove all query parameters."""
        return self._rebuild(query={})

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return self.get()

    def __repr__(self) -> str:
        return f"Uriable({self.get()!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Uriable):
            return self.get() == other.get()
        if isinstance(other, str):
            return self.get() == other
        return NotImplemented


class Uri:
    """Static factory and utility for fluent URI manipulation.

    Example::

        from fastapi_startkit.support.uri import Uri

        uri = Uri.of("https://api.example.com/v1/users?active=true")
        new_uri = (
            uri.append_path("search")
               .add_query("q", "alice")
               .with_scheme("http")
               .get()
        )
        # "http://api.example.com/v1/users/search?active=true&q=alice"
    """

    @classmethod
    def of(cls, url: str) -> Uriable:
        """Parse *url* and return a fluent :class:`Uriable` builder."""
        return Uriable(urlparse(url))

    @classmethod
    def parse(cls, url: str) -> Uriable:
        """Alias for :meth:`of`."""
        return cls.of(url)

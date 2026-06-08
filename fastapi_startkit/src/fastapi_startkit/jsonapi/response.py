"""JSON:API specification response classes.

https://jsonapi.org

Quick-start::

    from fastapi_startkit.jsonapi import JsonResource

    # Zero-config: auto-type from class name, auto-attributes from model.serialize()
    class PostResource(JsonResource["Post"]):
        pass

    # Override attributes or hide sensitive fields
    class UserResource(JsonResource["User"]):
        hidden = ["password", "remember_token"]

    # Add extra top-level envelope keys
    class ArticleResource(JsonResource["Article"]):
        def with_(self):
            return {"meta": {"version": "1.0"}}

    # Single resource
    @app.get("/api/posts/{id}")
    async def get_post(id: int):
        post = await Post.find_or_fail(id)
        return PostResource(post)

    # Collection (plain list or paginator)
    @app.get("/api/posts")
    async def list_posts():
        posts = await Post.all()
        return PostResource.collection(posts)

    # Paginated collection
    @app.get("/api/posts")
    async def list_posts_paginated(page: int = 1):
        posts = await Post.paginate(15, page)   # returns LengthAwarePaginator
        return PostResource.collection(posts)   # meta{total, per_page, ...} added automatically

Both classes implement the ASGI ``__call__`` protocol, so they can be
returned from FastAPI endpoints without any extra wiring.  ``?include=`` and
``fields[*]=`` query params are parsed automatically from the live request.

You can also call ``serialize()`` manually when you need the dict::

    doc = UserResource(user).serialize(
        include=["posts"],
        fields={"users": ["name"], "posts": ["title"]},
    )
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from urllib.parse import unquote_plus

import inflection

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Query-param helpers
# ---------------------------------------------------------------------------


def parse_include(param: str | None) -> list[str]:
    """Parse ``?include=author,comments`` into ``["author", "comments"]``.

    Follows the JSON:API spec comma-separated format.  Whitespace is stripped;
    empty segments and ``None`` return an empty list.

    :param param: raw query-string value or ``None``.
    :returns: list of relationship names to sideload.

    Example FastAPI usage::

        from fastapi import Query
        from fastapi_startkit.jsonapi import parse_include

        @app.get("/api/posts/{id}")
        async def get_post(id: int, include: str | None = Query(None)):
            post = await Post.find(id)
            return PostResource(post).serialize(include=parse_include(include))
    """
    if not param:
        return []
    return [name.strip() for name in param.split(",") if name.strip()]


def parse_fields(raw_query: dict[str, str]) -> dict[str, list[str]]:
    """Parse ``fields[posts]=title,body&fields[users]=name`` sparse fieldsets.

    The JSON:API spec uses the ``fields[type]`` family of query params to
    restrict which attributes are returned for each resource type.

    :param raw_query: flat ``{key: value}`` dict of ALL query parameters
                      (e.g. ``dict(request.query_params)`` in FastAPI).
    :returns: ``{resource_type: [field, ...]}`` for every ``fields[*]`` key.

    Example FastAPI usage::

        from fastapi import Request
        from fastapi_startkit.jsonapi import parse_fields

        @app.get("/api/posts/{id}")
        async def get_post(id: int, request: Request):
            fields = parse_fields(dict(request.query_params))
            # GET ?fields[posts]=title,body&fields[users]=name
            # -> {"posts": ["title", "body"], "users": ["name"]}
            post = await Post.find(id)
            return PostResource(post).serialize(fields=fields)
    """
    result: dict[str, list[str]] = {}
    for key, value in raw_query.items():
        if key.startswith("fields[") and key.endswith("]"):
            resource_type = key[7:-1].strip()
            if resource_type:
                result[resource_type] = [f.strip() for f in value.split(",") if f.strip()]
    return result


# ---------------------------------------------------------------------------
# ASGI mixin — makes resources directly returnable from FastAPI endpoints
# ---------------------------------------------------------------------------

# FastAPI checks `isinstance(response, starlette.responses.Response)` on every
# endpoint return value.  If True, it calls `await response(scope, receive, send)`
# directly.  If False, it JSON-serialises the raw object __dict__.
#
# We therefore make _FastAPICallable a real Response subclass when starlette is
# available, and fall back to plain `object` otherwise (serialize() still works,
# the user just can't return the resource directly from FastAPI).

try:
    from starlette.responses import Response as _StarletteResponse

    class _FastAPICallable(_StarletteResponse):
        """Starlette Response subclass that lazily serializes on ``__call__``.

        Subclasses (UserResource, PostResource, ...) have their own ``__init__``
        and never call ``super().__init__()``, so we must NOT rely on Starlette's
        ``Response.__init__`` having run.  We set the attributes FastAPI reads
        before calling ``__call__`` as class-level defaults, and we completely
        override ``__call__`` to handle ASGI ourselves.
        """

        # FastAPI reads `response.background` before calling `__call__`.
        # Setting it at class level ensures it's always present.
        background = None
        status_code = 200
        media_type = "application/vnd.api+json"

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            import json as _json

            # Parse query string from the ASGI scope.
            raw_qs: str = (scope.get("query_string") or b"").decode()
            qp: dict[str, str] = {}
            if raw_qs:
                for pair in raw_qs.split("&"):
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        qp[unquote_plus(k)] = unquote_plus(v)

            include = parse_include(qp.get("include"))
            fields = parse_fields(qp)

            body = _json.dumps(
                self.serialize(include=include, fields=fields)  # type: ignore[attr-defined]
            ).encode("utf-8")

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        [b"content-type", b"application/vnd.api+json"],
                        [b"content-length", str(len(body)).encode()],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})

except ImportError:  # starlette / fastapi not installed

    class _FastAPICallable:  # type: ignore[no-redef]
        """No-op when starlette is not installed.

        ``serialize()`` still works; returning the resource directly from a
        FastAPI endpoint will not until ``fastapi-startkit[fastapi]`` is installed.
        """


# ---------------------------------------------------------------------------
# JsonResource — generic base class
# ---------------------------------------------------------------------------


class JsonResource(Generic[T], _FastAPICallable):
    """Generic base class for a single JSON:API resource.

    Pass the model directly::

        class PostResource(JsonResource[Post]):
            pass  # auto-type="posts", auto-attributes from Post.serialize()

        class UserResource(JsonResource[User]):
            hidden = ["password"]  # strip sensitive fields from auto-serialize

        class ArticleResource(JsonResource[Article]):
            def with_(self):
                return {"meta": {"version": "1.0"}}  # extra top-level keys

    Class-level attributes
    ----------------------
    type : str
        Resource type string.  Auto-derived from the class name when not set
        (``AgentResource`` -> ``"agents"``).
    id : int | str
        Resource identifier.  Auto-set from ``model.id`` in ``__init__``.
    hidden : list[str]
        Field names to exclude from ``to_attributes()`` when auto-serializing
        via ``model.serialize()``.

    Class methods
    -------------
    collection(items)
        Wrap a plain list **or** a ``LengthAwarePaginator`` / ``SimplePaginator``
        in a :class:`_ResourceCollection`.  Pagination meta is included
        automatically.

    Overridable hooks
    -----------------
    to_attributes()    -- ``{name: value}`` dict of resource attributes
    to_relationships() -- ``{name: JsonResource}`` related resources
    to_links()         -- top-level links dict
    to_meta()          -- top-level meta dict
    with_()            -- extra top-level envelope keys merged into the document
    """

    # ------------------------------------------------------------------
    # Class-level defaults
    # ------------------------------------------------------------------

    type: str = ""
    id: int | str = ""
    hidden: list[str] = []
    relationships: dict[str, "JsonResource"] = {}

    # ------------------------------------------------------------------
    # Auto-type derivation
    # ------------------------------------------------------------------

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Auto-derive the JSON:API resource type from the class name when
        # the subclass does not define 'type' explicitly.
        # e.g. AgentResource -> "agents", UserProfileResource -> "user_profiles"
        if "type" not in cls.__dict__:
            name = cls.__name__.removesuffix("Resource")
            if name:
                cls.type = inflection.tableize(name)

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self, model: T) -> None:
        """Wrap *model* as a JSON:API resource.

        :param model: ORM model (or any object with an ``id`` attribute and
                      optionally a ``serialize()`` method).
        """
        self.model = model
        self.id = getattr(model, "id", "")

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def to_attributes(self) -> dict | None:
        """Return a ``{name: value}`` dict of resource attributes.

        Calls ``self.model.serialize()`` and strips ``"id"`` plus any names in
        ``self.hidden``.  Returns ``None`` when the model has no
        ``serialize()`` method or when the resulting dict is empty.
        """
        model = getattr(self, "model", None)
        if model is not None and hasattr(model, "serialize"):
            data = model.serialize()
            if isinstance(data, dict):
                blacklist = {"id"} | set(self.__class__.hidden)
                filtered = {k: v for k, v in data.items() if k not in blacklist}
                return filtered or None
        return None

    def to_relationships(self) -> dict[str, "JsonResource"] | None:
        """Return a ``{name: JsonResource}`` dict of related resources.

        The default implementation returns the class-level
        ``relationships`` dict only when its values are already
        ``JsonResource`` instances.  Override this to build the dict
        dynamically from an ORM object.
        """
        rels = self.__class__.relationships
        if not rels:
            return None
        return rels if all(isinstance(v, JsonResource) for v in rels.values()) else None

    def to_links(self) -> dict | None:
        """Return a ``{name: url}`` dict of links, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return a ``{name: value}`` meta dict, or ``None``."""
        return None

    def with_(self) -> dict:
        """Return extra keys to merge into the top-level JSON:API envelope.

        Use this to inject top-level ``meta``, ``links``, or any custom key
        alongside ``data``::

            class ArticleResource(JsonResource[Article]):
                def with_(self):
                    return {
                        "meta": {"version": "1.0"},
                    }

        The returned dict is shallow-merged into the document **after**
        ``to_links()`` / ``to_meta()`` are applied, so keys from ``with_()``
        can override them.

        :returns: dict of extra top-level envelope keys (default: ``{}``).
        """
        return {}

    # ------------------------------------------------------------------
    # Internal serialization helpers
    # ------------------------------------------------------------------

    def _build_data(self, fields: dict[str, list[str]] | None = None) -> dict:
        """Build the ``data`` member of the JSON:API document.

        :param fields: sparse-fieldset map from :func:`parse_fields`.
                       When present, only the listed fields are included in
                       ``data.attributes`` for each resource type.
        """
        data: dict[str, Any] = {
            "type": self.type,
            "id": str(self.id),
        }

        attrs = self.to_attributes()
        if attrs is not None:
            if fields and self.type in fields:
                allowed = fields[self.type]
                attrs = {k: v for k, v in attrs.items() if k in allowed}
            data["attributes"] = attrs

        rel_objs = self.to_relationships()
        if rel_objs:
            data["relationships"] = {
                name: {"data": {"type": resource.type, "id": str(resource.id)}} for name, resource in rel_objs.items()
            }

        return data

    def _collect_included(
        self,
        include: list[str],
        seen: set[str] | None = None,
        fields: dict[str, list[str]] | None = None,
    ) -> list[dict]:
        """Recursively sideload related resources.

        :param include: relationship names to sideload.
        :param seen: de-duplication set of ``"type:id"`` keys.
        :param fields: sparse-fieldset filter.
        """
        if seen is None:
            seen = set()

        included: list[dict] = []
        rel_objs = self.to_relationships() or {}

        for name, resource in rel_objs.items():
            if name not in include:
                continue

            key = f"{resource.type}:{resource.id}"
            if key in seen:
                continue
            seen.add(key)
            included.append(resource._build_data(fields=fields))

            # Recurse for nested dot-notation includes (e.g. "author.company").
            nested = [part[len(name) + 1 :] for part in include if part.startswith(f"{name}.")]
            if nested:
                included.extend(resource._collect_included(nested, seen, fields=fields))

        return included

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def serialize(
        self,
        include: list[str] | None = None,
        fields: dict[str, list[str]] | None = None,
    ) -> dict:
        """Serialize this resource into a JSON:API document dict.

        :param include: relationship names to sideload into ``included[]``.
                        Use comma-separated names via :func:`parse_include`,
                        or pass a plain list.  Dot notation is supported for
                        nested relationships (``"author.company"``).
        :param fields: sparse-fieldset map produced by :func:`parse_fields`.
                       Only the listed attribute names are included for each
                       resource type:
                       ``{"posts": ["title"], "users": ["name"]}``.

        :returns: A dict safe to return from any FastAPI endpoint or pass
                  to ``JSONResponse``.

        Typical FastAPI endpoint (manual)::

            @app.get("/api/posts/{id}")
            async def get_post(
                id: int,
                request: Request,
                include: str | None = Query(None),
            ):
                post = await Post.find(id)
                return PostResource(post).serialize(
                    include=parse_include(include),
                    fields=parse_fields(dict(request.query_params)),
                )

        Or simply return the resource directly and let FastAPI handle it::

            @app.get("/api/posts/{id}")
            async def get_post(id: int):
                post = await Post.find(id)
                return PostResource(post)
        """
        if include is None:
            include = []

        document: dict[str, Any] = {"data": self._build_data(fields=fields)}

        if include:
            included = self._collect_included(include, fields=fields)
            if included:
                document["included"] = included

        links = self.to_links()
        if links is not None:
            document["links"] = links

        meta = self.to_meta()
        if meta is not None:
            document["meta"] = meta

        # Merge any extra top-level keys from with_()
        extra = self.with_()
        if extra:
            document.update(extra)

        return document

    # ------------------------------------------------------------------
    # Collection factory
    # ------------------------------------------------------------------

    @classmethod
    def collection(cls, items: Any) -> "_ResourceCollection":
        """Wrap *items* in a :class:`_ResourceCollection`.

        *items* may be:

        * A plain ``list`` or iterable of model instances — each is wrapped
          with ``cls(model)``.
        * A ``LengthAwarePaginator`` or ``SimplePaginator`` — items are
          extracted and pagination meta (``total``, ``per_page``, ...) is
          included automatically in the response envelope.

        Example::

            posts = await Post.all()
            return PostResource.collection(posts)

            # Paginated
            posts = await Post.paginate(15, page)
            return PostResource.collection(posts)
        """
        try:
            from fastapi_startkit.masoniteorm.pagination.BasePaginator import (
                BasePaginator,
            )

            if isinstance(items, BasePaginator):
                resource_items = [cls(model) for model in items]
                return _ResourceCollection(resource_items, paginator=items)
        except ImportError:
            pass

        return _ResourceCollection([cls(model) for model in items])


# ---------------------------------------------------------------------------
# _ResourceCollection
# ---------------------------------------------------------------------------


class _ResourceCollection(_FastAPICallable):
    """Wraps a list of :class:`JsonResource` instances as a JSON:API collection.

    Prefer creating instances via :meth:`JsonResource.collection` rather
    than directly instantiating this class::

        return PostResource.collection(posts)

    Pagination meta is added automatically when the source is a paginator.
    Override :meth:`to_meta` / :meth:`to_links` to add custom envelope data.
    """

    def __init__(self, items: list[JsonResource], paginator: Any = None) -> None:
        self._items = items
        self._paginator = paginator

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def to_links(self) -> dict | None:
        """Return top-level links, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return top-level meta dict, or ``None``.

        Populated automatically from a paginator when present; override to
        customise or extend.
        """
        if self._paginator is None:
            return None

        paginator = self._paginator
        meta: dict[str, Any] = {}
        for attr in (
            "total",
            "count",
            "per_page",
            "current_page",
            "last_page",
            "next_page",
            "previous_page",
        ):
            if hasattr(paginator, attr):
                meta[attr] = getattr(paginator, attr)

        return meta if meta else None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(
        self,
        include: list[str] | None = None,
        fields: dict[str, list[str]] | None = None,
    ) -> dict:
        """Serialize the collection into a JSON:API document dict.

        :param include: relationship names to sideload (same semantics as
                        :meth:`JsonResource.serialize`).
        :param fields: sparse-fieldset map from :func:`parse_fields`.
        """
        if include is None:
            include = []

        document: dict[str, Any] = {
            "data": [item._build_data(fields=fields) for item in self._items],
        }

        if include:
            seen: set[str] = set()
            all_included: list[dict] = []
            for item in self._items:
                all_included.extend(item._collect_included(include, seen, fields=fields))
            if all_included:
                document["included"] = all_included

        links = self.to_links()
        if links is not None:
            document["links"] = links

        meta = self.to_meta()
        if meta is not None:
            document["meta"] = meta

        return document

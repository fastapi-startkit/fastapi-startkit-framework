"""JSON:API specification response classes.

https://jsonapi.org

Quick-start::

    from fastapi_startkit.jsonapi import JsonResource

    class PostResource(JsonResource["Post"]):
        pass  # auto-type="posts", auto-attributes from Post.serialize()

    class UserResource(JsonResource["User"]):
        hidden = ["password", "remember_token"]

    class ArticleResource(JsonResource["Article"]):
        def with_(self):
            return {"meta": {"version": "1.0"}}

    # Single resource — returned directly; ?include= and ?fields[*]= are
    # parsed from the live request automatically.
    @app.get("/api/posts/{id}")
    async def get_post(id: int):
        post = await Post.find_or_fail(id)
        return PostResource(post)

    # Restrict fields and sideload relationships with the fluent chain API:
    @app.get("/api/posts/{id}")
    async def get_post(id: int):
        post = await Post.find_or_fail(id)
        return PostResource(post).include("author").fields("title", "users.name")

    # Collection (plain list or paginator)
    @app.get("/api/posts")
    async def list_posts():
        posts = await Post.all()
        return PostResource.collection(posts)

    # Paginated collection
    @app.get("/api/posts")
    async def list_posts_paginated(page: int = 1):
        posts = await Post.paginate(15, page)
        return PostResource.collection(posts)

    # Manual serialization when you need the dict:
    doc = PostResource(post).include("author").fields("title", "users.name").serialize()
"""

from __future__ import annotations

import inspect
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

try:
    from starlette.responses import Response as _StarletteResponse

    class _FastAPICallable(_StarletteResponse):
        """Starlette Response subclass that lazily serializes on ``__call__``.

        If chain state has been set via ``.include()`` / ``.fields()`` before
        the resource is returned from an endpoint, that state is used.
        Otherwise the query string is parsed from the ASGI scope and passed
        to ``serialize()`` automatically.
        """

        background = None
        status_code = 200
        media_type = "application/vnd.api+json"

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            import json as _json

            # If chain methods were called before returning this resource,
            # _chain_state_set is True and we use that state directly.
            # Otherwise fall back to parsing ?include= and ?fields[*]= from the URL.
            if not getattr(self, "_chain_state_set", False):
                raw_qs: str = (scope.get("query_string") or b"").decode()
                qp: dict[str, str] = {}
                if raw_qs:
                    for pair in raw_qs.split("&"):
                        if "=" in pair:
                            k, _, v = pair.partition("=")
                            qp[unquote_plus(k)] = unquote_plus(v)
                # Temporarily set chain state from query string for this render.
                self._chain_include = parse_include(qp.get("include"))  # type: ignore[attr-defined]
                self._chain_fields = parse_fields(qp)  # type: ignore[attr-defined]

            body = _json.dumps(
                self.serialize()  # type: ignore[attr-defined]
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

except ImportError:

    class _FastAPICallable:  # type: ignore[no-redef]
        """No-op when starlette is not installed."""


# ---------------------------------------------------------------------------
# JsonResource — generic base class
# ---------------------------------------------------------------------------


class JsonResource(Generic[T], _FastAPICallable):
    """Generic base class for a single JSON:API resource.

    Pass the model directly::

        class PostResource(JsonResource[Post]):
            pass  # auto-type="posts", auto-attributes from Post.serialize()

        class UserResource(JsonResource[User]):
            hidden = ["password"]  # strip sensitive fields

        class ArticleResource(JsonResource[Article]):
            def with_(self):
                return {"meta": {"version": "1.0"}}

    Fluent chain API::

        # Sideload relationships
        return PostResource(post).include("author", "comments")

        # Restrict attributes — plain names apply to this resource's type;
        # dotted names ("type.field") apply to a related resource's type.
        return PostResource(post).fields("title", "created_at", "users.name")

        # Chain include + fields
        return PostResource(post).include("author").fields("title", "users.name")

        # Manual serialization
        doc = PostResource(post).include("author").fields("title", "users.name").serialize()

    When returned directly from a FastAPI endpoint with no chain methods called,
    ``?include=`` and ``?fields[*]=`` query params are parsed automatically
    from the live request.

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
        in a :class:`ResourceCollection`.  Pagination meta is included
        automatically.

    Overridable hooks
    -----------------
    to_attributes()    -- ``{name: value}`` dict of resource attributes
    to_relationships() -- ``{name: JsonResource}`` related resources
    to_links()         -- top-level links dict
    to_meta()          -- top-level meta dict
    with_()            -- extra top-level envelope keys merged into the document
    """

    type: str = ""
    id: int | str = ""
    hidden: list[str] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "type" not in cls.__dict__:
            name = cls.__name__.removesuffix("Resource")
            if name:
                cls.type = inflection.tableize(name)

    def __init__(self, model: T) -> None:
        self.model = model
        self.id = getattr(model, "id", "")
        self._chain_include: list[str] = []
        self._chain_fields: dict[str, list[str]] = {}
        self._chain_state_set: bool = False

    # ------------------------------------------------------------------
    # Fluent chain API
    # ------------------------------------------------------------------

    def include(self, *relationships: str) -> "JsonResource[T]":
        """Sideload one or more relationships into ``included[]``.

        Dot-notation is supported for nested relationships::

            PostResource(post).include("author", "author.company")

        :param relationships: relationship names to sideload.
        :returns: ``self`` for chaining.
        """
        self._chain_include = list(relationships)
        self._chain_state_set = True
        return self

    def fields(self, *field_specs: str) -> "JsonResource[T]":
        """Restrict which attributes are returned (JSON:API sparse fieldsets).

        Each argument is either a plain field name or a ``"type.field"`` spec:

        * Plain name (``"title"``) — restricts this resource's own attributes.
        * Dotted name (``"users.name"``) — restricts the named related type.

        Example::

            PostResource(post).fields("title", "created_at", "users.name")
            # → {"posts": ["title", "created_at"], "users": ["name"]}

        :param field_specs: field names, optionally prefixed with ``type.``.
        :returns: ``self`` for chaining.
        """
        for spec in field_specs:
            if "." in spec:
                rel_type, _, field = spec.partition(".")
                self._chain_fields.setdefault(rel_type, []).append(field)
            else:
                self._chain_fields.setdefault(self.type, []).append(spec)
        self._chain_state_set = True
        return self

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def to_attributes(self) -> dict | None:
        """Return a ``{name: value}`` dict of resource attributes.

        Calls ``self.model.serialize()`` and strips any names listed in
        ``self.hidden``.  All other fields are included as-is.
        Returns ``None`` when the model has no ``serialize()`` method or
        when the resulting dict is empty.
        """
        model = getattr(self, "model", None)
        if model is not None and hasattr(model, "serialize"):
            data = model.serialize()
            if isinstance(data, dict):
                blacklist = set(self.__class__.hidden)
                filtered = {k: v for k, v in data.items() if k not in blacklist}
                return filtered or None
        return None

    def to_relationships(self) -> dict | None:
        """Return a relationship mapping, or ``None``.

        Each value can be any of three forms:

        * **Resource class** — the framework reads ``self.model.<key>`` and
          wraps it automatically.  If the attribute is a list or ORM
          Collection, ``.collection()`` is called; otherwise the item is
          wrapped as a single resource::

              def to_relationships(self):
                  return {
                      "author":   UserResource,    # single → UserResource(model.author)
                      "comments": CommentResource, # list  → CommentResource.collection(model.comments)
                  }

        * **Lambda / function** — called with no arguments.  A returned list
          is automatically wrapped in :class:`ResourceCollection`::

              def to_relationships(self):
                  return {
                      "comments": lambda: [CommentResource(c) for c in self.model.comments],
                  }

        * **Plain list** of ``JsonResource`` instances — auto-wrapped::

              def to_relationships(self):
                  return {
                      "comments": [CommentResource(c) for c in self.model.comments],
                  }

        * **``JsonResource`` / ``ResourceCollection`` instance** — used as-is::

              def to_relationships(self):
                  return {"author": UserResource(self.model.author)}

        Returns ``None`` (no relationships) by default.
        """
        return None

    def to_links(self) -> dict | None:
        """Return a ``{name: url}`` dict of links, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return a ``{name: value}`` meta dict, or ``None``."""
        return None

    def with_(self) -> dict:
        """Return extra keys to merge into the top-level JSON:API envelope.

        Keys from ``with_()`` are shallow-merged last, so they take
        precedence over ``to_links()`` / ``to_meta()``::

            class ArticleResource(JsonResource[Article]):
                def with_(self):
                    return {"meta": {"version": "1.0"}}

        :returns: dict of extra top-level envelope keys (default: ``{}``).
        """
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_many(obj: Any) -> bool:
        """Return True when *obj* represents a collection of models.

        Matches plain lists/tuples, and ORM ``Collection`` objects (which store
        their items in ``_items``).  Single model instances are not iterable
        in this sense, so they return False.

        Note: ``hasattr()`` is deliberately avoided here.  ORM models override
        ``__getattr__`` to return ``None`` for any unknown attribute, which
        would make ``hasattr(model, "_items")`` incorrectly return ``True``.
        Checking ``obj.__dict__`` bypasses ``__getattr__`` and only returns
        True when ``_items`` is actually stored on the instance.
        """
        if isinstance(obj, (list, tuple)):
            return True
        try:
            return "_items" in obj.__dict__ and not isinstance(obj, ResourceCollection)
        except AttributeError:
            return False

    def _resolve_rel(self, key: str, value: Any) -> "JsonResource | ResourceCollection | None":
        """Resolve one relationship value to a concrete resource / collection.

        Supported forms — the framework picks the right wrapper automatically:

        * **Resource class** — attribute is a single model → ``Class(model.key)``;
          attribute is a list / ORM Collection → ``Class.collection(model.key)``::

              return {"author": UserResource, "comments": CommentResource}

        * **Lambda / function** — called with no args; a returned list is
          auto-wrapped in :class:`ResourceCollection`::

              return {"comments": lambda: [CommentResource(c) for c in self.model.comments]}

        * **Plain list** of ``JsonResource`` instances — auto-wrapped::

              return {"comments": [CommentResource(c) for c in self.model.comments]}

        * **``JsonResource`` / ``ResourceCollection`` instance** — used as-is::

              return {"author": UserResource(self.model.author)}
        """
        # --- class reference ---
        if isinstance(value, type):
            related = getattr(self.model, key, None) if hasattr(self, "model") else None
            if related is None:
                return None
            if self._is_many(related):
                return value.collection(related)
            return value(related)

        # --- lambda / plain function ---
        if inspect.isfunction(value) or inspect.ismethod(value):
            result = value()
            if isinstance(result, list):
                return ResourceCollection(result)
            return result

        # --- plain list of JsonResource instances ---
        if isinstance(value, list):
            return ResourceCollection(value)

        # --- already a JsonResource or ResourceCollection instance ---
        return value

    def _resolved_relationships(self) -> "dict[str, JsonResource | ResourceCollection]":
        """Return ``to_relationships()`` with all values resolved to instances."""
        raw = self.to_relationships()
        if not raw:
            return {}
        resolved: dict[str, Any] = {}
        for key, val in raw.items():
            result = self._resolve_rel(key, val)
            if result is not None:
                resolved[key] = result
        return resolved

    def _build_data(self, fields: dict[str, list[str]] | None = None) -> dict:
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

        rel_objs = self._resolved_relationships()
        if rel_objs:
            rels: dict[str, Any] = {}
            for name, resource in rel_objs.items():
                if isinstance(resource, ResourceCollection):
                    rels[name] = {"data": [{"type": item.type, "id": str(item.id)} for item in resource._items]}
                else:
                    rels[name] = {"data": {"type": resource.type, "id": str(resource.id)}}
            data["relationships"] = rels

        return data

    def _collect_included(
        self,
        include: list[str],
        seen: set[str] | None = None,
        fields: dict[str, list[str]] | None = None,
    ) -> list[dict]:
        if seen is None:
            seen = set()

        included: list[dict] = []
        rel_objs = self._resolved_relationships()

        for name, resource in rel_objs.items():
            if name not in include:
                continue
            # Handle collection relationships
            items = resource._items if isinstance(resource, ResourceCollection) else [resource]
            nested = [part[len(name) + 1 :] for part in include if part.startswith(f"{name}.")]
            for item in items:
                key = f"{item.type}:{item.id}"
                if key in seen:
                    continue
                seen.add(key)
                included.append(item._build_data(fields=fields))
                if nested:
                    included.extend(item._collect_included(nested, seen, fields=fields))

        return included

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> dict:
        """Serialize this resource into a JSON:API document dict.

        Uses the include / fields state set via the chain API::

            doc = PostResource(post).include("author").fields("posts", ["title"]).serialize()

        When returned directly from a FastAPI endpoint without calling chain
        methods, ``?include=`` and ``?fields[*]=`` query params are parsed
        from the live HTTP request automatically.

        :returns: A dict safe to pass to ``JSONResponse`` or return from
                  any FastAPI endpoint.
        """
        include = self._chain_include
        fields = self._chain_fields or None

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

        extra = self.with_()
        if extra:
            document.update(extra)

        return document

    # ------------------------------------------------------------------
    # Collection factory
    # ------------------------------------------------------------------

    @classmethod
    def collection(cls, items: Any) -> "ResourceCollection":
        """Wrap *items* in a :class:`ResourceCollection`.

        *items* may be:

        * A plain ``list`` or iterable of model instances.
        * A ``LengthAwarePaginator`` or ``SimplePaginator`` — pagination
          meta is included automatically in the response envelope.

        Example::

            return PostResource.collection(posts)
            return PostResource.collection(posts).include("author")
            return PostResource.collection(paginator).fields("posts", ["title"])
        """
        try:
            from fastapi_startkit.masoniteorm.pagination.BasePaginator import BasePaginator

            if isinstance(items, BasePaginator):
                resource_items = [cls(model) for model in items]
                return ResourceCollection(resource_items, paginator=items, primary_type=cls.type)
        except ImportError:
            pass

        return ResourceCollection([cls(model) for model in items], primary_type=cls.type)


# ---------------------------------------------------------------------------
# ResourceCollection
# ---------------------------------------------------------------------------


class ResourceCollection(_FastAPICallable):
    """Wraps a list of :class:`JsonResource` instances as a JSON:API collection.

    Prefer creating instances via :meth:`JsonResource.collection`::

        return PostResource.collection(posts)
        return PostResource.collection(posts).include("author")
        return PostResource.collection(posts).fields("title", "users.name")

    Pagination meta is added automatically when the source is a paginator.
    Override :meth:`to_meta` / :meth:`to_links` to add custom envelope data.
    """

    def __init__(
        self,
        items: list[JsonResource],
        paginator: Any = None,
        primary_type: str = "",
    ) -> None:
        self._items = items
        self._paginator = paginator
        self._primary_type = primary_type
        self._chain_include: list[str] = []
        self._chain_fields: dict[str, list[str]] = {}
        self._chain_state_set: bool = False

    # ------------------------------------------------------------------
    # Fluent chain API
    # ------------------------------------------------------------------

    def include(self, *relationships: str) -> "ResourceCollection":
        """Sideload one or more relationships into ``included[]``.

        :param relationships: relationship names to sideload.
        :returns: ``self`` for chaining.
        """
        self._chain_include = list(relationships)
        self._chain_state_set = True
        return self

    def fields(self, *field_specs: str) -> "ResourceCollection":
        """Restrict which attributes are returned (JSON:API sparse fieldsets).

        Same dot-notation as :meth:`JsonResource.fields` — plain names apply
        to the primary resource type; ``"type.field"`` applies to a related type::

            PostResource.collection(posts).fields("title", "created_at", "users.name")

        :param field_specs: field names, optionally prefixed with ``type.``.
        :returns: ``self`` for chaining.
        """
        for spec in field_specs:
            if "." in spec:
                rel_type, _, field = spec.partition(".")
                self._chain_fields.setdefault(rel_type, []).append(field)
            else:
                self._chain_fields.setdefault(self._primary_type, []).append(spec)
        self._chain_state_set = True
        return self

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def to_links(self) -> dict | None:
        """Return top-level links, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return top-level meta dict, or ``None``.

        Auto-populated from a paginator when present.
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

    def serialize(self) -> dict:
        """Serialize the collection into a JSON:API document dict.

        Uses the include / fields state set via the chain API.
        """
        include = self._chain_include
        fields = self._chain_fields or None

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

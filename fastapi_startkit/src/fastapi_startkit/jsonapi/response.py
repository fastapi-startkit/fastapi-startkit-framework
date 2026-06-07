"""JSON:API specification response classes.

https://jsonapi.org

Usage::

    from fastapi_startkit.jsonapi import JsonAPIResponse, JsonAPIListResponse

    class PostResource(JsonAPIResponse):
        type = "posts"
        attributes = ["title", "body"]
        relationships = {"author": UserResource}

        def __init__(self, post):
            self._obj = post
            self.id = post.id

        def to_attributes(self):
            return {"title": self._obj.title, "body": self._obj.body}

        def to_relationships(self):
            return {"author": UserResource(self._obj.author)}
"""

from __future__ import annotations

from typing import Any


class JsonAPIResponse:
    """Base class for a single JSON:API resource.

    Subclasses must define:
        type (str)      – resource type (e.g. ``"posts"``)
        id   (int|str)  – resource identifier

    Optionally declare:
        attributes (list[str])                   – field names exposed in
                                                   ``data.attributes``
        relationships (dict[str, JsonAPIResponse]) – related resources
    """

    # Subclasses set these as class-level defaults; instances may override.
    type: str = ""
    id: int | str = ""
    attributes: list[str] = []
    relationships: dict[str, "JsonAPIResponse"] = {}

    # ------------------------------------------------------------------
    # Overridable hooks
    # ------------------------------------------------------------------

    def to_attributes(self) -> dict | None:
        """Return a dict of attribute name → value.

        Default implementation builds the dict from ``self.attributes`` by
        reading matching instance attributes (or ``None`` when absent).
        """
        if not self.attributes:
            return None
        return {
            attr: getattr(self, attr, None)
            for attr in self.attributes
        }

    def to_relationships(self) -> dict[str, "JsonAPIResponse"] | None:
        """Return a dict of relationship name → ``JsonAPIResponse`` instance.

        Default implementation returns ``self.relationships`` when it is a
        dict of instances (not class references).  Override to build the
        dict dynamically.
        """
        rels = self.__class__.relationships  # class-level dict
        if not rels:
            return None
        # If values are *instances* (not classes) return as-is.
        return rels if all(
            isinstance(v, JsonAPIResponse) for v in rels.values()
        ) else None

    def to_links(self) -> dict | None:
        """Return a dict of link name → URL, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return a dict of meta information, or ``None``."""
        return None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _build_data(self) -> dict:
        """Build the ``data`` member of the JSON:API document."""
        data: dict[str, Any] = {
            "type": self.type,
            "id": str(self.id),
        }

        attrs = self.to_attributes()
        if attrs is not None:
            data["attributes"] = attrs

        rel_objs = self.to_relationships()
        if rel_objs:
            data["relationships"] = {
                name: {
                    "data": {
                        "type": resource.type,
                        "id": str(resource.id),
                    }
                }
                for name, resource in rel_objs.items()
            }

        return data

    def _collect_included(
        self, include: list[str], seen: set[str] | None = None
    ) -> list[dict]:
        """Recursively collect sideloaded resources into a flat list.

        :param include: relationship names to sideload (e.g. ``["author"]``).
        :param seen: set of ``"type:id"`` strings already added (prevents
                     duplicates across nested includes).
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
            included.append(resource._build_data())

            # Recurse for nested relationships using dot notation.
            nested_includes = [
                part[len(name) + 1:]
                for part in include
                if part.startswith(f"{name}.")
            ]
            if nested_includes:
                included.extend(
                    resource._collect_included(nested_includes, seen)
                )

        return included

    def serialize(self, include: list[str] | None = None) -> dict:
        """Serialize this resource into a JSON:API document dict.

        :param include: list of relationship names to sideload into the
                        ``included`` top-level member.  Dot notation is
                        supported for nested relationships
                        (e.g. ``["author.comments"]``).

        :returns: A dict that is safe to return directly from a FastAPI
                  endpoint or pass to ``JSONResponse``.
        """
        if include is None:
            include = []

        document: dict[str, Any] = {
            "data": self._build_data(),
        }

        if include:
            included = self._collect_included(include)
            if included:
                document["included"] = included

        links = self.to_links()
        if links is not None:
            document["links"] = links

        meta = self.to_meta()
        if meta is not None:
            document["meta"] = meta

        return document


class JsonAPIListResponse:
    """Wraps a list of :class:`JsonAPIResponse` instances.

    Usage::

        resource = JsonAPIListResponse([
            PostResource(post) for post in posts
        ])
        return resource.serialize(include=["author"])
    """

    def __init__(self, items: list[JsonAPIResponse]) -> None:
        self._items = items

    def to_links(self) -> dict | None:
        """Return top-level links, or ``None``."""
        return None

    def to_meta(self) -> dict | None:
        """Return top-level meta, or ``None``."""
        return None

    def serialize(self, include: list[str] | None = None) -> dict:
        """Serialize the list of resources into a JSON:API document dict.

        :param include: relationship names to sideload (same semantics as
                        :meth:`JsonAPIResponse.serialize`).
        """
        if include is None:
            include = []

        document: dict[str, Any] = {
            "data": [item._build_data() for item in self._items],
        }

        if include:
            seen: set[str] = set()
            all_included: list[dict] = []
            for item in self._items:
                all_included.extend(item._collect_included(include, seen))
            if all_included:
                document["included"] = all_included

        links = self.to_links()
        if links is not None:
            document["links"] = links

        meta = self.to_meta()
        if meta is not None:
            document["meta"] = meta

        return document

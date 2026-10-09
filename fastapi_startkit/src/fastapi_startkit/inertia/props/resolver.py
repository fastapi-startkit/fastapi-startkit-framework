import copy
import inspect
import logging
import time
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Optional

from fastapi import Request

from fastapi_startkit.inertia.constant import Header
from fastapi_startkit.inertia.props.props import Loading, MergeOptions, OnceOptions, Prop
from fastapi_startkit.inertia.props.scroll import ScrollMetadata, scroll_metadata_of, serialize_page

logger = logging.getLogger(__name__)


@dataclass
class Metadata:
    shared_props: list[str] = field(default_factory=list)
    merge_props: list[str] = field(default_factory=list)
    prepend_props: list[str] = field(default_factory=list)
    deep_merge_props: list[str] = field(default_factory=list)
    match_props_on: list[str] = field(default_factory=list)
    deferred_props: dict[str, list[str]] = field(default_factory=dict)
    rescued_props: list[str] = field(default_factory=list)
    scroll_props: dict[str, dict] = field(default_factory=dict)
    once_props: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        page = {
            "sharedProps": self.shared_props,
            "mergeProps": self.merge_props,
            "prependProps": self.prepend_props,
            "deepMergeProps": self.deep_merge_props,
            "matchPropsOn": self.match_props_on,
            "deferredProps": self.deferred_props,
            "rescuedProps": self.rescued_props,
            "scrollProps": self.scroll_props,
            "onceProps": self.once_props,
        }
        return {key: value for key, value in page.items() if value}


@dataclass
class Resolved:
    value: Any
    nested: bool = False
    computed: bool = False
    scroll: Optional[ScrollMetadata] = None


async def invoke(callback: Any, request: Request) -> Any:
    value = callback(request) if inspect.signature(callback).parameters else callback()
    if inspect.isawaitable(value):
        value = await value
    return value


def header_list(request: Request, name: str) -> Optional[list[str]]:
    values = [value.strip() for value in (request.headers.get(name) or "").split(",")]
    values = [value for value in values if value]
    return values or None


def is_within(path: str, ancestor: str) -> bool:
    return path == ancestor or path.startswith(ancestor + ".")


def unpack_dot_keys(props: dict) -> dict:
    unpacked = {key: value for key, value in props.items() if "." not in key}
    for key in [key for key in props if "." in key]:
        unpacked = set_path(unpacked, key.split("."), props[key], "")
    return unpacked


def set_path(container: Mapping, segments: list[str], value: Any, prefix: str) -> dict:
    first, *rest = segments
    path = f"{prefix}.{first}" if prefix else first
    updated = dict(container)
    updated[first] = merge_into(updated.get(first), rest, value, path) if rest else value
    return updated


def merge_into(parent: Any, segments: list[str], value: Any, path: str) -> Any:
    if parent is None:
        return set_path({}, segments, value, path)
    if isinstance(parent, Mapping):
        return set_path(parent, segments, value, path)
    if isinstance(parent, Prop):
        combined = copy.copy(parent)
        combined.value = merge_into(parent.value, segments, value, path)
        return combined
    if callable(parent):

        async def resolve_then_merge(request: Request) -> Any:
            return merge_into(await invoke(parent, request), segments, value, path)

        return resolve_then_merge
    raise TypeError(f"Cannot set Inertia prop '{path}.{'.'.join(segments)}': '{path}' is not a mapping")


class PropsResolver:
    def __init__(self, request: Request, component: str):
        self.request = request
        partial_component = request.headers.get(Header.INERTIA_PARTIAL_COMPONENT)
        self.is_partial = bool(partial_component) and partial_component == component
        self.is_inertia = bool(request.headers.get(Header.INERTIA))
        self.only = header_list(request, Header.INERTIA_PARTIAL_DATA)
        self.except_ = header_list(request, Header.INERTIA_PARTIAL_EXCEPT)
        self.reset = header_list(request, Header.INERTIA_RESET) or []
        self.except_once = header_list(request, Header.INERTIA_EXCEPT_ONCE_PROPS) or []
        self.prepends_scroll = request.headers.get(Header.INERTIA_INFINITE_SCROLL_MERGE_INTENT) == "prepend"
        self.metadata = Metadata()

    async def resolve(self, shared: dict, props: dict, expose_shared_keys: bool = True) -> tuple[dict, dict]:
        if expose_shared_keys:
            for key in shared:
                top = key.split(".")[0]
                if top not in self.metadata.shared_props:
                    self.metadata.shared_props.append(top)

        resolved = await self._resolve_level(unpack_dot_keys({**shared, **props}), "", False)
        return resolved, self.metadata.to_dict()

    async def _resolve_level(self, props: Mapping, prefix: str, parent_was_resolved: bool) -> dict:
        resolved = {}
        for key, value in props.items():
            prop = value if isinstance(value, Prop) else Prop(value)
            path = f"{prefix}.{key}" if prefix else str(key)

            if not self._is_included_in_partial_reload(prop, path, parent_was_resolved):
                continue

            if self._is_excluded(prop, path):
                self._collect_excluded_metadata(prop, path)
                continue

            try:
                result = await self._compute(prop, path)
            except Exception:
                if not prop.is_rescued:
                    raise
                logger.exception("Rescued Inertia prop %s that failed to resolve", path)
                self.metadata.rescued_props.append(path)
                continue

            self._collect_metadata(prop, path, result.scroll)

            if result.nested:
                resolved[key] = await self._resolve_level(
                    result.value, path, parent_was_resolved or prop.is_always or result.computed
                )
            else:
                resolved[key] = result.value
        return resolved

    async def _compute(self, prop: Prop, path: str) -> Resolved:
        value = prop.value
        if isinstance(value, Mapping):
            return Resolved(value, nested=True)

        computed = callable(value)
        if computed:
            value = await self._call(value, path)

        scroll = None
        if prop.scroll_options is not None:
            scroll = prop.scroll_options.metadata or scroll_metadata_of(value)
            value = serialize_page(value)
            computed = True

        return Resolved(value, nested=computed and isinstance(value, Mapping), computed=computed, scroll=scroll)

    async def _call(self, callback: Any, path: str) -> Any:
        value = await invoke(callback, self.request)
        seen: set[int] = set()
        while isinstance(value, Prop):
            if id(value) in seen:
                raise ValueError(f"Inertia prop '{path}' resolves to a Prop that references itself")
            seen.add(id(value))
            if value.has_options():
                warnings.warn(
                    f"Inertia prop '{path}' returned a Prop with options; they are ignored, "
                    "set them on the outer prop instead",
                    stacklevel=2,
                )
            value = await invoke(value.value, self.request) if callable(value.value) else value.value
        return value

    def _is_included_in_partial_reload(self, prop: Prop, path: str, parent_was_resolved: bool) -> bool:
        return not self.is_partial or prop.is_always or parent_was_resolved or self._matches_partial_reload(path)

    def _matches_partial_reload(self, path: str) -> bool:
        if self.only is not None and not self._is_on_requested_path(path):
            return False
        return not self._is_excepted(path)

    def _contributes_partial_metadata(self, path: str) -> bool:
        if self.only is not None and not self._is_requested(path):
            return False
        return not self._is_excepted(path)

    def _is_requested(self, path: str) -> bool:
        return self.only is not None and any(is_within(path, only) for only in self.only)

    def _is_on_requested_path(self, path: str) -> bool:
        return self.only is not None and any(is_within(path, only) or is_within(only, path) for only in self.only)

    def _is_excepted(self, path: str) -> bool:
        return self.except_ is not None and any(is_within(path, excepted) for excepted in self.except_)

    def _is_excluded(self, prop: Prop, path: str) -> bool:
        if self.is_partial:
            return self._was_already_loaded(prop, path) and not self._is_on_requested_path(path)
        return prop.loading != Loading.EAGER or (self.is_inertia and self._was_already_loaded(prop, path))

    def _was_already_loaded(self, prop: Prop, path: str) -> bool:
        once = prop.once_options
        return once is not None and not once.fresh and (once.key or path) in self.except_once

    def _collect_excluded_metadata(self, prop: Prop, path: str) -> None:
        if prop.loading == Loading.DEFERRED and not self._was_already_loaded(prop, path):
            self.metadata.deferred_props.setdefault(prop.group_name, []).append(path)

        if prop.loading != Loading.EAGER and prop.merge_options is not None:
            self._collect_merge_metadata(prop.merge_options, path)

        if prop.once_options is not None:
            self._collect_once_metadata(prop.once_options, path)

    def _collect_metadata(self, prop: Prop, path: str, scroll: Optional[ScrollMetadata]) -> None:
        if prop.merge_options is not None:
            self._collect_merge_metadata(self._effective_merge(prop, prop.merge_options), path)

        if scroll is not None:
            self.metadata.scroll_props[path] = {**scroll.to_dict(), "reset": path in self.reset}

        if prop.once_options is not None:
            self._collect_once_metadata(prop.once_options, path)

    def _effective_merge(self, prop: Prop, merge: MergeOptions) -> MergeOptions:
        if prop.scroll_options is None:
            return merge
        if self.prepends_scroll:
            return replace(merge, prepends_at=[*merge.prepends_at, prop.wrapper_key])
        return replace(merge, appends_at=[*merge.appends_at, prop.wrapper_key])

    def _collect_merge_metadata(self, merge: MergeOptions, path: str) -> None:
        if path in self.reset:
            return

        if merge.deep:
            targets = [(self.metadata.deep_merge_props, path)]
        elif merge.merges_at_root():
            targets = [(self.metadata.merge_props if merge.append else self.metadata.prepend_props, path)]
        else:
            targets = [(self.metadata.merge_props, f"{path}.{at}") for at in merge.appends_at]
            targets += [(self.metadata.prepend_props, f"{path}.{at}") for at in merge.prepends_at]

        emitted = False
        for paths, target in targets:
            merged_paths = self._merge_paths_in_response(target)
            paths.extend(merged_paths)
            emitted = emitted or bool(merged_paths)

        if emitted:
            self.metadata.match_props_on.extend(f"{path}.{key}" for key in merge.match_on)

    def _merge_paths_in_response(self, target: str) -> list[str]:
        if not self.is_partial:
            return [target]
        if self._is_excepted(target):
            return []
        if self.only is None or self._is_requested(target):
            return [target]
        return [only for only in self.only if is_within(only, target) and not self._is_excepted(only)]

    def _collect_once_metadata(self, once: OnceOptions, path: str) -> None:
        if self.is_partial and not self._contributes_partial_metadata(path):
            return

        expires_at = None
        if once.ttl is not None:
            expires_at = (int(time.time()) + int(once.ttl.total_seconds())) * 1000

        self.metadata.once_props[once.key or path] = {"prop": path, "expiresAt": expires_at}

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Optional, Self, Union

from fastapi_startkit.inertia.props.scroll import ScrollMetadata


class Loading(Enum):
    EAGER = "eager"
    OPTIONAL = "optional"
    DEFERRED = "deferred"


@dataclass
class MergeOptions:
    deep: bool = False
    append: bool = True
    appends_at: list[str] = field(default_factory=list)
    prepends_at: list[str] = field(default_factory=list)
    match_on: list[str] = field(default_factory=list)

    def merges_at_root(self) -> bool:
        return not self.appends_at and not self.prepends_at


@dataclass
class OnceOptions:
    key: Optional[str] = None
    ttl: Optional[timedelta] = None
    fresh: bool = False


@dataclass
class ScrollOptions:
    metadata: Optional[ScrollMetadata] = None


class Prop:
    def __init__(self, value: Any = None):
        self.value = value
        self.loading = Loading.EAGER
        self.group_name = "default"
        self.is_always = False
        self.is_rescued = False
        self.merge_options: Optional[MergeOptions] = None
        self.once_options: Optional[OnceOptions] = None
        self.scroll_options: Optional[ScrollOptions] = None
        self.wrapper_key = "data"

    def optional(self) -> Self:
        self.loading = Loading.OPTIONAL
        return self

    def defer(self, group: str = "default") -> Self:
        return self.group(group)

    def group(self, name: str) -> Self:
        self.loading = Loading.DEFERRED
        self.group_name = name
        return self

    def always(self) -> Self:
        self.is_always = True
        return self

    def rescue(self) -> Self:
        self.is_rescued = True
        return self

    def merge(self) -> Self:
        self._merge()
        return self

    def deep_merge(self) -> Self:
        self._merge().deep = True
        return self

    def append(self) -> Self:
        self._merge().append = True
        return self

    def prepend(self) -> Self:
        self._merge().append = False
        return self

    def append_at(self, path: str) -> Self:
        self._merge().appends_at.append(path)
        return self

    def prepend_at(self, path: str) -> Self:
        self._merge().prepends_at.append(path)
        return self

    def match_on(self, key: str) -> Self:
        self._merge().match_on.append(key)
        return self

    def once(self) -> Self:
        self._once()
        return self

    def once_as(self, key: str) -> Self:
        self._once().key = key
        return self

    def until(self, ttl: Union[timedelta, int, float]) -> Self:
        self._once().ttl = ttl if isinstance(ttl, timedelta) else timedelta(seconds=ttl)
        return self

    def fresh(self) -> Self:
        self._once().fresh = True
        return self

    def wrapper(self, key: str) -> Self:
        self.wrapper_key = key
        return self

    def scroll(self, metadata: Optional[ScrollMetadata] = None) -> Self:
        self._merge()
        self.scroll_options = ScrollOptions(metadata=metadata)
        return self

    def _merge(self) -> MergeOptions:
        if self.merge_options is None:
            self.merge_options = MergeOptions()
        return self.merge_options

    def _once(self) -> OnceOptions:
        if self.once_options is None:
            self.once_options = OnceOptions()
        return self.once_options


class OptionalProp(Prop):
    def __init__(self, callback):
        super().__init__(callback)
        self.optional()

    @property
    def callback(self):
        return self.value

    def __call__(self):
        return self.value()

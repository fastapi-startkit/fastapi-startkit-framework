from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class ScrollMetadata:
    page_name: str
    previous_page: Any = None
    next_page: Any = None
    current_page: Any = None

    @classmethod
    def pages(cls, page_name: str, current_page: int, last_page: int) -> "ScrollMetadata":
        return cls(
            page_name=page_name,
            previous_page=current_page - 1 if current_page > 1 else None,
            next_page=current_page + 1 if current_page < last_page else None,
            current_page=current_page,
        )

    @classmethod
    def cursors(
        cls,
        cursor_name: str,
        previous: Optional[str] = None,
        next: Optional[str] = None,
        current: Optional[str] = None,
    ) -> "ScrollMetadata":
        return cls(
            page_name=cursor_name,
            previous_page=previous,
            next_page=next,
            current_page=current if current is not None else 1,
        )

    def to_dict(self) -> dict:
        return {
            "pageName": self.page_name,
            "previousPage": self.previous_page,
            "nextPage": self.next_page,
            "currentPage": self.current_page,
        }


@runtime_checkable
class ProvidesScrollMetadata(Protocol):
    def scroll_metadata(self) -> ScrollMetadata: ...


def scroll_metadata_of(page: Any) -> Optional[ScrollMetadata]:
    if isinstance(page, ProvidesScrollMetadata):
        return page.scroll_metadata()
    if all(hasattr(page, name) for name in ("current_page", "previous_page", "next_page")):
        return ScrollMetadata(
            page_name=getattr(page, "page_name", "page"),
            previous_page=page.previous_page,
            next_page=page.next_page,
            current_page=page.current_page,
        )
    return None


def serialize_page(page: Any) -> Any:
    serialize = getattr(page, "serialize", None)
    return serialize() if callable(serialize) else page

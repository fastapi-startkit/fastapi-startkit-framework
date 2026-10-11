from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from fastapi import Request

current_request: ContextVar[Optional[Request]] = ContextVar("inertia_request", default=None)


@dataclass
class InertiaRequestState:
    shared_props: dict[str, Any] = field(default_factory=dict)
    root_view: Optional[str] = None
    version: Optional[Callable[[], Optional[str]]] = None
    resolved_version: Optional[str] = None
    version_resolved: bool = False
    encrypt_history: Optional[bool] = None
    session: dict[str, Any] = field(default_factory=dict)


current_state: ContextVar[Optional[InertiaRequestState]] = ContextVar("inertia_state", default=None)

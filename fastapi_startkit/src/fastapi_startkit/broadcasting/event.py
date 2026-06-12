from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from fastapi_startkit.application import app

if TYPE_CHECKING:
    pass


class ShouldBroadcast(ABC):
    @abstractmethod
    def broadcast_on(self) -> list: ...


class BroadcastEvent(ShouldBroadcast):
    """Base class for all broadcastable events.

    Subclasses must implement ``broadcast_on()`` returning a list of Channel
    objects.  At dispatch time the event is pushed to every channel in that
    list using the configured broadcast driver.

    Attributes:
        payload: Arbitrary data dict sent to subscribers.  Defaults to an
            empty dict; subclasses can populate it in ``__init__`` or by
            overriding ``broadcast_with()``.
        name: Event name seen by subscribers.  Defaults to the class name at
            emit time.  Override to use a custom string.
    """

    payload: dict = {}
    name: str | None = None

    # ------------------------------------------------------------------
    # Driver-layer helpers (used by ReverbDriver / LogDriver)
    # ------------------------------------------------------------------

    def broadcast_as(self) -> str:
        """Return the event name used on the wire.

        Uses ``self.name`` when set; otherwise falls back to the class name.
        """
        return self.name if self.name is not None else self.__class__.__name__

    def broadcast_with(self) -> dict:
        """Return the payload dict.

        Returns ``self.payload`` when it is non-empty; otherwise serialises
        all instance attributes (backward-compatible behaviour).
        """
        if self.payload:
            return dict(self.payload)
        return {k: v for k, v in self.__dict__.items()}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def emit(self) -> None:
        """Dispatch this event via the BroadcastManager.

        Resolves the ``"broadcasting"`` service directly from the Application
        container — no facade in the call chain.

        Equivalent to::

            from fastapi_startkit.application import app
            await app().make("broadcasting").dispatch(self)
        """
        manager = app().make("broadcasting")
        await manager.dispatch(self)

"""Optional base class for class-based listeners.

Listeners are not required to extend this — any callable, or any class exposing
a ``handle`` method, works. It exists to document the contract and to give
type checkers something to lean on. ``handle`` may be sync or async.
"""

from abc import ABC, abstractmethod
from typing import Any


class Listener(ABC):
    @abstractmethod
    def handle(self, event: Any):
        """Handle the given event."""
        ...

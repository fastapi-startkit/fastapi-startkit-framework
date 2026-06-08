from abc import ABC, abstractmethod


class ShouldBroadcast(ABC):
    @abstractmethod
    def broadcast_on(self) -> list: ...


class BroadcastEvent(ShouldBroadcast):
    def broadcast_as(self) -> str:
        return self.__class__.__name__

    def broadcast_with(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

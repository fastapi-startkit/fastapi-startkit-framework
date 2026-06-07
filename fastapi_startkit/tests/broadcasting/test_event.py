import pytest
from abc import ABC
from fastapi_startkit.broadcasting.event import BroadcastEvent, ShouldBroadcast
from fastapi_startkit.broadcasting.channels import Channel


class OrderShipped(BroadcastEvent):
    def __init__(self, order_id: int):
        self.order_id = order_id

    def broadcast_on(self):
        return [Channel(f"orders.{self.order_id}")]


def test_broadcast_as_returns_class_name():
    event = OrderShipped(1)
    assert event.broadcast_as() == "OrderShipped"


def test_broadcast_with_returns_instance_dict():
    event = OrderShipped(42)
    assert event.broadcast_with() == {"order_id": 42}


def test_broadcast_with_multiple_fields():
    class MultiEvent(BroadcastEvent):
        def __init__(self):
            self.a = 1
            self.b = "hello"

        def broadcast_on(self):
            return [Channel("test")]

    event = MultiEvent()
    assert event.broadcast_with() == {"a": 1, "b": "hello"}


def test_should_broadcast_is_abc():
    assert issubclass(ShouldBroadcast, ABC)


def test_should_broadcast_requires_broadcast_on():
    with pytest.raises(TypeError):
        ShouldBroadcast()  # type: ignore[abstract]


def test_broadcast_event_broadcast_on_returns_channels():
    event = OrderShipped(7)
    channels = event.broadcast_on()
    assert len(channels) == 1
    assert channels[0].name == "orders.7"

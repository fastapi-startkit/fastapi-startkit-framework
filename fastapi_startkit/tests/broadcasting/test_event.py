"""Tests for broadcasting event base classes."""
import pytest
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent, ShouldBroadcast


class OrderShipped(BroadcastEvent):
    def __init__(self, order_id: int, status: str):
        self.order_id = order_id
        self.status = status

    def broadcast_on(self) -> list:
        return [Channel("orders")]


class TestBroadcastEvent:
    def test_broadcast_as_returns_class_name(self):
        event = OrderShipped(order_id=42, status="shipped")
        assert event.broadcast_as() == "OrderShipped"

    def test_broadcast_with_returns_instance_dict(self):
        event = OrderShipped(order_id=42, status="shipped")
        data = event.broadcast_with()
        assert data == {"order_id": 42, "status": "shipped"}

    def test_broadcast_on_returns_channels(self):
        event = OrderShipped(order_id=1, status="pending")
        channels = event.broadcast_on()
        assert len(channels) == 1
        assert channels[0].name == "orders"

    def test_should_broadcast_is_abstract(self):
        with pytest.raises(TypeError):
            ShouldBroadcast()

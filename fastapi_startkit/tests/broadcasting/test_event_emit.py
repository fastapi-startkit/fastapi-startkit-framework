"""Tests for the new BroadcastEvent.payload / .name / .emit() API (Task #147)."""
import pytest
from unittest.mock import MagicMock, patch

from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SimpleEvent(BroadcastEvent):
    def broadcast_on(self):
        return [Channel("test")]


class EventWithPayload(BroadcastEvent):
    payload = {"order_id": 42}

    def broadcast_on(self):
        return [Channel("orders")]


class EventWithName(BroadcastEvent):
    name = "custom.event"

    def broadcast_on(self):
        return [Channel("test")]


# ---------------------------------------------------------------------------
# payload attribute
# ---------------------------------------------------------------------------

def test_broadcast_event_default_payload_is_empty_dict():
    event = SimpleEvent()
    assert event.payload == {}


def test_broadcast_event_payload_returned_by_broadcast_with():
    event = EventWithPayload()
    assert event.broadcast_with() == {"order_id": 42}


def test_broadcast_event_broadcast_with_falls_back_to_instance_attrs_when_payload_empty():
    class EventWithAttr(BroadcastEvent):
        def __init__(self):
            self.foo = "bar"

        def broadcast_on(self):
            return [Channel("x")]

    event = EventWithAttr()
    # payload is empty (default), so instance attrs are returned
    assert event.broadcast_with() == {"foo": "bar"}


# ---------------------------------------------------------------------------
# name attribute
# ---------------------------------------------------------------------------

def test_broadcast_event_default_name_is_none():
    event = SimpleEvent()
    assert event.name is None


def test_broadcast_as_uses_name_when_set():
    event = EventWithName()
    assert event.broadcast_as() == "custom.event"


def test_broadcast_as_falls_back_to_class_name_when_name_is_none():
    event = SimpleEvent()
    assert event.broadcast_as() == "SimpleEvent"


# ---------------------------------------------------------------------------
# emit()
# ---------------------------------------------------------------------------

def test_emit_calls_broadcast_dispatch():
    """emit() should delegate to Broadcast.dispatch(self)."""
    event = SimpleEvent()

    mock_broadcast = MagicMock()
    mock_broadcast.dispatch = MagicMock()

    # The import is lazy (inside the method), so patch at the facades module level
    with patch("fastapi_startkit.facades.Broadcast.Broadcast", mock_broadcast):
        event.emit()

    mock_broadcast.dispatch.assert_called_once_with(event)

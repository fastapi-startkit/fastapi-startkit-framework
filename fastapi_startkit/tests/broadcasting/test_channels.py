"""Tests for broadcasting Channel classes."""
import pytest
from fastapi_startkit.broadcasting.channels import Channel, PrivateChannel, PresenceChannel


class TestChannel:
    def test_channel_stores_name(self):
        ch = Channel("orders")
        assert ch.name == "orders"

    def test_channel_repr(self):
        ch = Channel("orders")
        assert "orders" in repr(ch)


class TestPrivateChannel:
    def test_private_channel_prefixes_private(self):
        ch = PrivateChannel("orders")
        assert ch.name == "private-orders"

    def test_private_channel_is_channel(self):
        ch = PrivateChannel("orders")
        assert isinstance(ch, Channel)


class TestPresenceChannel:
    def test_presence_channel_prefixes_presence(self):
        ch = PresenceChannel("chat")
        assert ch.name == "presence-chat"

    def test_presence_channel_is_channel(self):
        ch = PresenceChannel("chat")
        assert isinstance(ch, Channel)

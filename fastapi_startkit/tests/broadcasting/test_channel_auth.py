"""Tests for the ChannelAuthRegistry and @Broadcast.channel() decorator (Task #148)."""

import pytest

from fastapi_startkit.broadcasting.auth import ChannelAuthRegistry


# ---------------------------------------------------------------------------
# Pattern-matching helpers (smoke tests)
# ---------------------------------------------------------------------------


def test_exact_channel_match():
    registry = ChannelAuthRegistry()

    @registry.channel("orders.42")
    async def authorize(user):
        return True

    # Should find the pattern and match
    result = registry._find("orders.42")
    assert result is not None


def test_wildcard_channel_match():
    registry = ChannelAuthRegistry()

    @registry.channel("orders.{order_id}")
    async def authorize(user, order_id: int):
        return True

    result = registry._find("orders.99")
    assert result is not None
    callback, kwargs = result
    assert kwargs == {"order_id": "99"}


def test_no_match_returns_none():
    registry = ChannelAuthRegistry()
    assert registry._find("unknown.channel") is None


# ---------------------------------------------------------------------------
# Authorization — public channels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_channel_no_rule_allowed():
    registry = ChannelAuthRegistry()
    # No callback registered; public channel = allow
    assert await registry.authorize("orders.1", user=None) is True


@pytest.mark.asyncio
async def test_public_channel_with_allowing_rule():
    registry = ChannelAuthRegistry()

    @registry.channel("orders.{id}")
    async def auth(user, id: str):
        return True

    assert await registry.authorize("orders.1", user=None) is True


# ---------------------------------------------------------------------------
# Authorization — private channels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_channel_no_rule_denied():
    registry = ChannelAuthRegistry()
    assert await registry.authorize("private-orders.1", user=None) is False


@pytest.mark.asyncio
async def test_private_channel_with_allowing_callback():
    registry = ChannelAuthRegistry()

    @registry.channel("private-orders.{order_id}")
    async def auth(user, order_id: int):
        return user is not None

    class FakeUser:
        pass

    assert await registry.authorize("private-orders.1", user=FakeUser()) is True


@pytest.mark.asyncio
async def test_private_channel_with_denying_callback():
    registry = ChannelAuthRegistry()

    @registry.channel("private-orders.{order_id}")
    async def auth(user, order_id: int):
        return False

    assert await registry.authorize("private-orders.1", user=object()) is False


# ---------------------------------------------------------------------------
# Authorization — presence channels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_presence_channel_no_rule_denied():
    registry = ChannelAuthRegistry()
    assert await registry.authorize("presence-room.42", user=None) is False


@pytest.mark.asyncio
async def test_presence_channel_with_allowing_callback():
    registry = ChannelAuthRegistry()

    @registry.channel("presence-room.{room_id}")
    async def auth(user, room_id: str):
        return True

    assert await registry.authorize("presence-room.42", user=object()) is True


# ---------------------------------------------------------------------------
# Wildcard type casting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wildcard_cast_to_int():
    registry = ChannelAuthRegistry()
    received = {}

    @registry.channel("private-orders.{order_id}")
    async def auth(user, order_id: int):
        received["order_id"] = order_id
        return True

    await registry.authorize("private-orders.123", user=object())
    assert received["order_id"] == 123
    assert isinstance(received["order_id"], int)


# ---------------------------------------------------------------------------
# Sync callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_callback_supported():
    registry = ChannelAuthRegistry()

    @registry.channel("private-sync.{id}")
    def auth(user, id: str):
        return True

    assert await registry.authorize("private-sync.1", user=object()) is True


# ---------------------------------------------------------------------------
# BroadcastManager.channel() proxies to registry
# ---------------------------------------------------------------------------


def test_manager_channel_decorator_registers_callback():
    from fastapi_startkit.broadcasting.manager import BroadcastManager

    manager = BroadcastManager({"default": "log"})

    @manager.channel("private-test.{id}")
    async def auth(user, id: str):
        return True

    # The callback should be findable in the registry
    result = manager.channel_registry._find("private-test.99")
    assert result is not None

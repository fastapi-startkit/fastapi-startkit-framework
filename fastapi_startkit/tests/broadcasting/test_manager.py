"""Tests for BroadcastManager."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi_startkit.broadcasting.manager import BroadcastManager
from fastapi_startkit.broadcasting.drivers.log_driver import LogDriver
from fastapi_startkit.broadcasting.drivers.reverb_driver import ReverbDriver
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent


class SampleEvent(BroadcastEvent):
    def __init__(self):
        self.value = "test"

    def broadcast_on(self) -> list:
        return [Channel("sample")]


class TestBroadcastManagerDriverResolution:
    def test_driver_log_returns_log_driver(self):
        config = {"default": "log"}
        manager = BroadcastManager(config)
        assert isinstance(manager.driver("log"), LogDriver)

    def test_driver_reverb_returns_reverb_driver(self):
        config = {"default": "reverb"}
        mock_server = MagicMock()
        manager = BroadcastManager(config, server=mock_server)
        driver = manager.driver("reverb")
        assert isinstance(driver, ReverbDriver)
        assert driver.server is mock_server

    def test_driver_uses_default_when_no_name(self):
        config = {"default": "log"}
        manager = BroadcastManager(config)
        assert isinstance(manager.driver(), LogDriver)

    def test_driver_raises_for_unknown_driver(self):
        config = {"default": "unknown"}
        manager = BroadcastManager(config)
        with pytest.raises(ValueError, match="Unknown broadcast driver"):
            manager.driver("unknown")


class TestBroadcastManagerEvent:
    @pytest.mark.asyncio
    async def test_event_calls_driver_broadcast(self):
        config = {"default": "log"}
        manager = BroadcastManager(config)
        # Replace the driver's broadcast with a mock
        mock_broadcast = AsyncMock()
        manager.driver("log").broadcast = mock_broadcast  # won't persist — patch at class level

        # Use a real log driver but mock at manager level
        mock_driver = MagicMock()
        mock_driver.broadcast = AsyncMock()
        manager.driver = MagicMock(return_value=mock_driver)

        event = SampleEvent()
        await manager.event(event)

        manager.driver.assert_called_once_with()
        mock_driver.broadcast.assert_awaited_once_with(event)

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi_startkit.broadcasting.manager import BroadcastManager
from fastapi_startkit.broadcasting.drivers.log_driver import LogDriver
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent


class SampleEvent(BroadcastEvent):
    def __init__(self):
        self.value = 1

    def broadcast_on(self):
        return [Channel("test")]


def test_manager_resolves_log_driver():
    config = {"default": "log"}
    manager = BroadcastManager(config)
    driver = manager.driver()
    assert isinstance(driver, LogDriver)


def test_manager_resolves_log_driver_by_name():
    config = {"default": "reverb"}
    manager = BroadcastManager(config)
    driver = manager.driver("log")
    assert isinstance(driver, LogDriver)


def test_manager_resolves_reverb_driver():
    from fastapi_startkit.broadcasting.drivers.reverb_driver import ReverbDriver

    config = {"default": "reverb"}
    mock_server = MagicMock()
    manager = BroadcastManager(config, server=mock_server)
    driver = manager.driver("reverb")
    assert isinstance(driver, ReverbDriver)


def test_manager_raises_for_unknown_driver():
    config = {"default": "unknown"}
    manager = BroadcastManager(config)
    with pytest.raises(ValueError, match="Unknown broadcast driver"):
        manager.driver("unknown")


@pytest.mark.asyncio
async def test_manager_event_calls_broadcast():
    config = {"default": "log"}
    manager = BroadcastManager(config)
    event = SampleEvent()

    mock_driver = AsyncMock()
    with patch.object(manager, "driver", return_value=mock_driver):
        await manager.event(event)
        mock_driver.broadcast.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_manager_uses_default_driver():
    config = {"default": "log"}
    manager = BroadcastManager(config)
    event = SampleEvent()

    with patch("fastapi_startkit.broadcasting.drivers.log_driver.logger") as mock_logger:
        await manager.event(event)
        assert mock_logger.info.called

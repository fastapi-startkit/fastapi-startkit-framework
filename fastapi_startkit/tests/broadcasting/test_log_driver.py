import pytest
from unittest.mock import patch
from fastapi_startkit.broadcasting.drivers.log_driver import LogDriver
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent


class UserJoined(BroadcastEvent):
    def __init__(self, user_id: int):
        self.user_id = user_id

    def broadcast_on(self):
        return [Channel("users")]


@pytest.mark.asyncio
async def test_log_driver_logs_correct_channel():
    driver = LogDriver()
    event = UserJoined(99)

    with patch("fastapi_startkit.broadcasting.drivers.log_driver.logger") as mock_logger:
        await driver.broadcast(event)
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "channel=users" in call_args


@pytest.mark.asyncio
async def test_log_driver_logs_correct_event_name():
    driver = LogDriver()
    event = UserJoined(1)

    with patch("fastapi_startkit.broadcasting.drivers.log_driver.logger") as mock_logger:
        await driver.broadcast(event)
        call_args = mock_logger.info.call_args[0][0]
        assert "event=UserJoined" in call_args


@pytest.mark.asyncio
async def test_log_driver_logs_correct_data():
    driver = LogDriver()
    event = UserJoined(42)

    with patch("fastapi_startkit.broadcasting.drivers.log_driver.logger") as mock_logger:
        await driver.broadcast(event)
        call_args = mock_logger.info.call_args[0][0]
        assert "42" in call_args


@pytest.mark.asyncio
async def test_log_driver_logs_each_channel():
    class MultiChannelEvent(BroadcastEvent):
        def broadcast_on(self):
            return [Channel("chan-a"), Channel("chan-b")]

        def broadcast_as(self):
            return "MultiChannelEvent"

        def broadcast_with(self):
            return {}

    driver = LogDriver()
    event = MultiChannelEvent()

    with patch("fastapi_startkit.broadcasting.drivers.log_driver.logger") as mock_logger:
        await driver.broadcast(event)
        assert mock_logger.info.call_count == 2

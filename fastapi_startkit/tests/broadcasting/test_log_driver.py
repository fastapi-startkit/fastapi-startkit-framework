"""Tests for broadcasting LogDriver."""
import logging
import pytest
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.drivers.log_driver import LogDriver
from fastapi_startkit.broadcasting.event import BroadcastEvent


class UserJoined(BroadcastEvent):
    def __init__(self, user_id: int):
        self.user_id = user_id

    def broadcast_on(self) -> list:
        return [Channel("users")]


class TestLogDriver:
    @pytest.mark.asyncio
    async def test_broadcast_logs_channel_event_data(self, caplog):
        driver = LogDriver()
        event = UserJoined(user_id=7)

        with caplog.at_level(logging.INFO, logger="reverb"):
            await driver.broadcast(event)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "channel=users" in record.message
        assert "event=UserJoined" in record.message
        assert "user_id" in record.message

    @pytest.mark.asyncio
    async def test_broadcast_logs_one_record_per_channel(self, caplog):
        class MultiChannelEvent(BroadcastEvent):
            def broadcast_on(self) -> list:
                return [Channel("ch1"), Channel("ch2")]

            def broadcast_with(self) -> dict:
                return {}

        driver = LogDriver()

        with caplog.at_level(logging.INFO, logger="reverb"):
            await driver.broadcast(MultiChannelEvent())

        assert len(caplog.records) == 2

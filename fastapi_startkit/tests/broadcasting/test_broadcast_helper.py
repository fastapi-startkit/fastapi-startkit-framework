import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent


class OrderShipped(BroadcastEvent):
    def __init__(self, order_id: int):
        self.order_id = order_id

    def broadcast_on(self):
        return [Channel(f"orders.{self.order_id}")]


@pytest.mark.asyncio
async def test_broadcast_helper_calls_manager_event():
    mock_manager = AsyncMock()
    mock_app = MagicMock()
    mock_app.return_value.make.return_value = mock_manager

    with patch("fastapi_startkit.broadcasting.helpers.app", mock_app):
        from fastapi_startkit.broadcasting.helpers import broadcast

        event = OrderShipped(1)
        await broadcast(event)
        mock_manager.event.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_broadcast_helper_resolves_broadcasting_key():
    mock_manager = AsyncMock()
    mock_app_instance = MagicMock()
    mock_app_instance.make.return_value = mock_manager
    mock_app = MagicMock(return_value=mock_app_instance)

    with patch("fastapi_startkit.broadcasting.helpers.app", mock_app):
        from fastapi_startkit.broadcasting.helpers import broadcast

        await broadcast(OrderShipped(2))
        mock_app_instance.make.assert_called_once_with("broadcasting")


@pytest.mark.asyncio
async def test_broadcast_helper_passes_event_to_manager():
    mock_manager = AsyncMock()
    mock_app_instance = MagicMock()
    mock_app_instance.make.return_value = mock_manager
    mock_app = MagicMock(return_value=mock_app_instance)

    with patch("fastapi_startkit.broadcasting.helpers.app", mock_app):
        from fastapi_startkit.broadcasting.helpers import broadcast

        event = OrderShipped(99)
        await broadcast(event)
        args = mock_manager.event.call_args[0]
        assert args[0] is event

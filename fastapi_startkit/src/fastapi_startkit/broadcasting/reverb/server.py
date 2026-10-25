import json

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .channel_manager import ChannelManager
from .connection import ConnectionManager
from .signature import requires_auth, valid_channel, verify

MESSAGE_TOO_BIG = 1009


class ReverbServer:
    max_message_size = 10_000

    def __init__(self, key: str = "local", secret: str = ""):
        self.key = key
        self.secret = secret
        self.connections = ConnectionManager()
        self.channels = ChannelManager()

    async def handle(self, websocket: WebSocket):
        await websocket.accept()
        socket_id = self.connections.add(websocket)
        try:
            await self._send(
                websocket,
                "pusher:connection_established",
                json.dumps({"socket_id": socket_id, "activity_timeout": 120}),
            )
            await self._receive_loop(socket_id, websocket)
        except WebSocketDisconnect:
            pass
        finally:
            self.connections.remove(socket_id)
            self.channels.remove_socket(socket_id)

    async def _receive_loop(self, socket_id: str, websocket: WebSocket):
        while True:
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                return
            text = frame.get("text")
            if text is not None and len(text) > self.max_message_size:
                await self._error(websocket, "Maximum message size exceeded")
                await websocket.close(code=MESSAGE_TOO_BIG)
                return
            message = self._parse(text)
            if message is None:
                await self._error(websocket, "Invalid message format")
                continue
            await self._handle_message(socket_id, websocket, message)

    @staticmethod
    def _parse(text: str | None) -> dict[str, object] | None:
        if text is None:
            return None
        try:
            message = json.loads(text)
        except ValueError:
            return None
        if not isinstance(message, dict) or not isinstance(message.get("event", ""), str):
            return None
        return message

    async def _handle_message(self, socket_id: str, websocket: WebSocket, message: dict[str, object]):
        event = message.get("event", "")
        if event == "pusher:ping":
            await self._send(websocket, "pusher:pong", {})
        elif event == "pusher:subscribe":
            await self._subscribe(socket_id, websocket, message.get("data"))

    async def _subscribe(self, socket_id: str, websocket: WebSocket, data: object):
        if not isinstance(data, dict) or not isinstance(data.get("channel"), str) or not data["channel"]:
            await self._error(websocket, "Invalid subscription")
            return
        channel = data["channel"]
        if not valid_channel(channel):
            await self._subscription_error(websocket, channel, "InvalidChannel", "Invalid channel name", 400)
            return
        if requires_auth(channel) and not verify(
            self.key, self.secret, socket_id, channel, data.get("auth"), data.get("channel_data")
        ):
            await self._subscription_error(websocket, channel, "AuthError", "Invalid signature", 401)
            return
        self.channels.subscribe(channel, socket_id)
        await self._send(websocket, "pusher_internal:subscription_succeeded", {}, channel)

    async def _subscription_error(self, websocket: WebSocket, channel: str, kind: str, error: str, status: int):
        await self._send(
            websocket, "pusher:subscription_error", {"type": kind, "error": error, "status": status}, channel
        )

    async def _error(self, websocket: WebSocket, message: str):
        await self._send(websocket, "pusher:error", {"code": 4200, "message": message})

    @staticmethod
    async def _send(websocket: WebSocket, event: str, data: object, channel: str | None = None):
        payload: dict[str, object] = {"event": event, "data": data}
        if channel is not None:
            payload["channel"] = channel
        await websocket.send_text(json.dumps(payload))

    async def broadcast_to_channel(self, channel_name: str, event_name: str, data: dict[str, object]):
        payload = json.dumps({"event": event_name, "channel": channel_name, "data": data})
        for socket_id in self.channels.subscribers(channel_name):
            ws = self.connections.get(socket_id)
            if ws:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

    def as_starlette_app(self, app_key: str = "local") -> Starlette:
        async def endpoint(ws: WebSocket):
            await self.handle(ws)

        return Starlette(routes=[WebSocketRoute(f"/app/{app_key}", endpoint)])

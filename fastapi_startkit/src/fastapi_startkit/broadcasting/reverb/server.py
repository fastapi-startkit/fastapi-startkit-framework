import json
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.routing import WebSocketRoute
from starlette.applications import Starlette
from .connection import ConnectionManager
from .channel_manager import ChannelManager
from .signature import requires_auth, verify


class ReverbServer:
    def __init__(self, key: str = "local", secret: str = "secret"):
        self.key = key
        self.secret = secret
        self.connections = ConnectionManager()
        self.channels = ChannelManager()

    async def handle(self, websocket: WebSocket):
        await websocket.accept()
        socket_id = self.connections.add(websocket)
        await websocket.send_text(
            json.dumps(
                {
                    "event": "pusher:connection_established",
                    "data": json.dumps({"socket_id": socket_id, "activity_timeout": 120}),
                }
            )
        )
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                await self._handle_message(socket_id, websocket, message)
        except WebSocketDisconnect:
            self.connections.remove(socket_id)
            self.channels.remove_socket(socket_id)

    async def _handle_message(self, socket_id: str, websocket: WebSocket, message: dict):
        event = message.get("event", "")
        if event == "pusher:ping":
            await websocket.send_text(json.dumps({"event": "pusher:pong", "data": {}}))
        elif event == "pusher:subscribe":
            data = message.get("data") or {}
            channel = data.get("channel", "")
            if not isinstance(channel, str) or not channel:
                return
            if requires_auth(channel) and not verify(
                self.key, self.secret, socket_id, channel, data.get("auth"), data.get("channel_data")
            ):
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "pusher:subscription_error",
                            "channel": channel,
                            "data": {"type": "AuthError", "error": "Invalid signature", "status": 401},
                        }
                    )
                )
                return
            self.channels.subscribe(channel, socket_id)
            await websocket.send_text(
                json.dumps({"event": "pusher_internal:subscription_succeeded", "channel": channel, "data": {}})
            )

    async def broadcast_to_channel(self, channel_name: str, event_name: str, data: dict):
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

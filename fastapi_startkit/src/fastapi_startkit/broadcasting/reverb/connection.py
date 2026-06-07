import uuid
from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    def add(self, websocket: WebSocket) -> str:
        socket_id = str(uuid.uuid4())
        self._connections[socket_id] = websocket
        return socket_id

    def remove(self, socket_id: str) -> None:
        self._connections.pop(socket_id, None)

    def get(self, socket_id: str):
        return self._connections.get(socket_id)

    def all(self) -> dict:
        return dict(self._connections)

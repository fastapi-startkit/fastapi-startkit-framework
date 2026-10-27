import secrets

from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    def add(self, websocket: WebSocket) -> str:
        socket_id = self._new_socket_id()
        while socket_id in self._connections:
            socket_id = self._new_socket_id()
        self._connections[socket_id] = websocket
        return socket_id

    @staticmethod
    def _new_socket_id() -> str:
        return f"{secrets.randbelow(10**10)}.{secrets.randbelow(10**10)}"

    def remove(self, socket_id: str) -> None:
        self._connections.pop(socket_id, None)

    def get(self, socket_id: str):
        return self._connections.get(socket_id)

    def all(self) -> dict[str, WebSocket]:
        return dict(self._connections)

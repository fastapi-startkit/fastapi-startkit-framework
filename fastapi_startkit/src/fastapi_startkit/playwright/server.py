import asyncio
import importlib
import socket
from contextlib import contextmanager
from typing import Any

from typing_extensions import Self


def load_app(target: Any) -> Any:
    if isinstance(target, str):
        module_name, _, attribute = target.partition(":")
        target = getattr(importlib.import_module(module_name), attribute or "app")

    fastapi = getattr(target, "fastapi", None)
    return target if fastapi is None else fastapi


def embedded_server(app: Any) -> Any:
    import uvicorn

    class EmbeddedServer(uvicorn.Server):
        @contextmanager
        def capture_signals(self):
            yield

    return EmbeddedServer(uvicorn.Config(load_app(app), log_level="warning"))


class LiveServer:
    def __init__(self, app: Any, host: str = "127.0.0.1", startup_timeout: float = 10.0):
        self.app = app
        self.host = host
        self.startup_timeout = startup_timeout
        self.port = 0
        self._server: Any = None
        self._socket: socket.socket | None = None
        self._task: "asyncio.Task[Any] | None" = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> Self:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, 0))
        self.port = self._socket.getsockname()[1]

        self._server = embedded_server(self.app)
        self._task = asyncio.get_running_loop().create_task(
            self._serve(self._server, self._socket), name="fastapi-startkit-live-server"
        )
        await self._wait_until_started()
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, self.startup_timeout)
            except asyncio.TimeoutError:
                pass
        if self._socket is not None:
            self._socket.close()
        self._server = None
        self._task = None
        self._socket = None

    @staticmethod
    async def _serve(server: Any, sock: socket.socket) -> None:
        try:
            await server.serve(sockets=[sock])
        except SystemExit:
            pass

    async def _wait_until_started(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.startup_timeout
        while not self._server.started:
            if not self.running:
                await self.stop()
                raise RuntimeError(f"The application server at {self.url} stopped before it started.")
            if loop.time() > deadline:
                await self.stop()
                raise RuntimeError(
                    f"The application server at {self.url} did not start within {self.startup_timeout}s."
                )
            await asyncio.sleep(0.01)

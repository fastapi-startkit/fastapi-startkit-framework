from cleo.helpers import option

from fastapi_startkit import Config
from fastapi_startkit.console.command import Command
from fastapi_startkit.environment import value as cast_value
from fastapi_startkit.support import Uri, Uriable


class ServeCommand(Command):
    name = "serve"
    description = "Start the FastAPI server."

    # WebSocket backends accepted by uvicorn's ``--ws`` option. ``auto`` is the
    # safe default: uvicorn only imports a concrete backend when a WebSocket
    # connection is actually opened, so serving never requires the optional
    # ``websockets`` package for apps that don't use WebSockets.
    WS_BACKENDS = ("auto", "none", "websockets", "websockets-sansio", "wsproto")
    DEFAULT_WS_BACKEND = "auto"

    options = [
        option(
            "port",
            "p",
            flag=False,
            default=None,
            description="The port to serve the application on (overrides fastapi config)",
        ),
        option(
            "host",
            None,
            flag=False,
            default=None,
            description="The host to bind to (overrides fastapi config)",
        ),
        option(
            "reload",
            "r",
            flag=False,
            default=None,
            description="Enable auto-reload on code changes (overrides fastapi config)",
        ),
        option(
            "app",
            "a",
            flag=False,
            default="bootstrap.application:app",
            description="The application to serve",
        ),
        option(
            "ws",
            None,
            flag=False,
            default=None,
            description=(
                "WebSocket backend passed to uvicorn: "
                "auto, none, websockets, websockets-sansio, wsproto. "
                "Defaults to 'auto' (overrides fastapi config)"
            ),
        ),
    ]

    def resolve_option(self, key: str, default: str | int | None = None):
        value = self.option(key) or Config.get(f"fastapi.{key}", default)

        return cast_value(value)

    def resolve_url(self) -> Uriable:
        host = self.option("host") or Config.get("fastapi.app_url", "http://127.0.0.1:8000")
        port = self.option("port")

        if host and not host.startswith("http"):
            host = f"http://{host}"

        uri = Uri.of(host)

        return uri.with_port(port) if port else uri

    def resolve_ws(self) -> str:
        """Select the uvicorn WebSocket backend: CLI flag > config > safe default."""
        return self.option("ws") or Config.get("fastapi.ws") or self.DEFAULT_WS_BACKEND

    def handle(self):
        import uvicorn

        from fastapi_startkit import Config
        from fastapi_startkit.container import Container

        ws = self.resolve_ws()
        if ws not in self.WS_BACKENDS:
            self.line(f"<error>Invalid --ws backend '{ws}'. Allowed values: {', '.join(self.WS_BACKENDS)}.</error>")
            return 1

        # Resolve server settings: CLI flag > fastapi config > uvicorn default (None)
        cfg_reload_dirs = Config.get("fastapi.reload_dirs") or None
        cfg_reload_excludes = Config.get("fastapi.reload_excludes") or None

        url = self.resolve_url()
        reload = self.resolve_option("reload", True)

        kwargs = {
            "host": url.host(),
            "port": url.port(),
            "reload": reload,
            "ws": ws,
        }

        if self.is_app_exist():
            kwargs.update(
                {
                    "app": self.option("app"),
                    "factory": True,
                }
            )
            if cfg_reload_dirs is not None and reload:
                kwargs["reload_dirs"] = cfg_reload_dirs
            if cfg_reload_excludes is not None and reload:
                kwargs["reload_excludes"] = cfg_reload_excludes

            self.line(f"<info>Starting Uvicorn server on {url.host()}:{url.port()} [{self.option('app')}]...</info>")

        else:
            self.line(f"<info>Starting Uvicorn server on {url.host()}:{url.port()}...</info>")
            kwargs.update({"app": Container.instance().fastapi, "reload": False})

        try:
            uvicorn.run(**kwargs)
        except KeyboardInterrupt:
            self.line("<comment>Server stopped manually.</comment>")

    def is_app_exist(self) -> "bool":
        import importlib.util

        app = self.option("app")

        module_name = app.split(":")[0]
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                return True
        except (ImportError, ValueError):
            pass

        self.line("<fg=yellow>Unable to detect the application, run the command with --app={app}</>")

        return False

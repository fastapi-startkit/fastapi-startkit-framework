from cleo.helpers import option
from fastapi_startkit.console.command import Command
from fastapi_startkit.support import Uri

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


class ServeCommand(Command):
    name = "serve"
    description = "Start the FastAPI server."

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
    ]

    def resolve_host_port(self) -> tuple[str, int]:
        """Return (host, port) applying the priority chain:

        CLI --host/--port  >  APP_HOST/APP_PORT (fastapi.host/port config)
        >  APP_URL (fastapi.app_url config)  >  built-in defaults.
        """
        from fastapi_startkit import Config

        host = _DEFAULT_HOST
        port = _DEFAULT_PORT

        # Layer 1: APP_URL — parse host and port from the URL when set.
        app_url = Config.get("fastapi.app_url", "") or ""
        if app_url:
            # Bare hosts like "myapp.com:9000" have no scheme; add one so
            # urlparse can extract hostname and port correctly.
            normalised = app_url if "://" in app_url else f"http://{app_url}"
            parsed = Uri.of(normalised)
            if parsed.host():
                host = parsed.host()
            if parsed.port():
                port = parsed.port()

        # Layer 2: APP_HOST / APP_PORT environment variables (via config fields).
        cfg_host = Config.get("fastapi.host", "") or ""
        cfg_port = Config.get("fastapi.port", 0) or 0
        if cfg_host:
            host = cfg_host
        if cfg_port:
            port = int(cfg_port)

        # Layer 3: CLI flags win over everything.
        cli_host = self.option("host")
        cli_port = self.option("port")
        if cli_host:
            host = cli_host
        if cli_port:
            port = int(cli_port)

        return host, port

    def handle(self):
        import uvicorn

        from fastapi_startkit import Config
        from fastapi_startkit.container import Container

        host, port = self.resolve_host_port()

        cfg_reload_dirs = Config.get("fastapi.reload_dirs") or None
        cfg_reload_excludes = Config.get("fastapi.reload_excludes") or None
        reload = Config.get("fastapi.reload", True) if self.option("reload") is None else self.option("reload")

        kwargs = {
            "host": host,
            "port": port,
            "reload": reload,
            "ws": "websockets-sansio",
        }

        if self.is_app_exist():
            kwargs.update(
                {
                    "app": self.option("app"),
                    "factory": True,
                }
            )
            if cfg_reload_dirs is not None:
                kwargs["reload_dirs"] = cfg_reload_dirs
            if cfg_reload_excludes is not None:
                kwargs["reload_excludes"] = cfg_reload_excludes

            self.line(f"<info>Starting Uvicorn server on {host}:{port} [{self.option('app')}]...</info>")

        else:
            self.line(f"<info>Starting Uvicorn server on {host}:{port}...</info>")
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

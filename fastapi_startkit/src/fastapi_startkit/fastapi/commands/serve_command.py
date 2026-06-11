from urllib.parse import urlparse

from cleo.helpers import option

from fastapi_startkit.console.command import Command


def _resolve_host_port(
    cfg_host: str | None,
    cfg_port: int | None,
    app_url: str | None,
) -> tuple[str, int]:
    """Resolve host and port with priority: APP_HOST/APP_PORT → APP_URL → defaults.

    Args:
        cfg_host: Value of APP_HOST (may be None).
        cfg_port: Value of APP_PORT (may be None).
        app_url:  Value of APP_URL (may be None).

    Returns:
        A (host, port) tuple always containing concrete values.
    """
    host = cfg_host or None
    port = int(cfg_port) if cfg_port else None

    if app_url and (not host or port is None):
        raw = app_url
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        if not host:
            host = parsed.hostname or None
        if port is None:
            port = parsed.port or None

    host = host or "127.0.0.1"
    port = port if port is not None else 8000

    return host, port


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

    def handle(self):
        import uvicorn
        from fastapi_startkit import Config
        from fastapi_startkit.container import Container

        # Read raw config values — no defaults here
        cfg_host = Config.get("fastapi.host")
        cfg_port = Config.get("fastapi.port")
        cfg_app_url = Config.get("fastapi.app_url")
        cfg_reload = Config.get("fastapi.reload", True)
        cfg_reload_dirs = Config.get("fastapi.reload_dirs") or None
        cfg_reload_excludes = Config.get("fastapi.reload_excludes") or None

        # Full resolution: APP_HOST/APP_PORT → APP_URL → 127.0.0.1/8000
        resolved_host, resolved_port = _resolve_host_port(cfg_host, cfg_port, cfg_app_url)

        # CLI flags override resolved config
        host = self.option("host") or resolved_host
        port = int(self.option("port") or resolved_port)
        reload = cfg_reload if self.option("reload") is None else self.option("reload")
        app = self.option("app")

        exist = self.is_app_exist()

        kwargs = {
            "host": host,
            "port": port,
            "reload": reload,
            "ws": "websockets-sansio",
        }

        if exist:
            kwargs.update(
                {
                    "app": app,
                    "factory": True,
                }
            )
            if cfg_reload_dirs is not None:
                kwargs["reload_dirs"] = cfg_reload_dirs
            if cfg_reload_excludes is not None:
                kwargs["reload_excludes"] = cfg_reload_excludes

            self.line(f"<info>Starting Uvicorn server on {host}:{port} [{app}]...</info>")

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

from cleo.helpers import option

from fastapi_startkit.console.command import Command
from fastapi_startkit.support import Uri


def _resolve_host_port(
    cfg_host: str | None,
    cfg_port: int | None,
    app_url: str | None,
    cli_host: str | None = None,
    cli_port: int | None = None,
) -> tuple[str, int]:
    """Resolve host and port with strict priority order.

    Priority (highest to lowest):
      1. CLI flags (``--host`` / ``--port``)
      2. Env vars APP_HOST / APP_PORT  (``cfg_host`` / ``cfg_port``)
      3. Parsed from APP_URL           (``app_url``)
      4. Hardcoded defaults            (``127.0.0.1`` / ``8000``)

    Args:
        cfg_host:  Value of APP_HOST env var (may be None).
        cfg_port:  Value of APP_PORT env var (may be None).
        app_url:   Value of APP_URL env var (may be None).
        cli_host:  Value passed via ``--host`` CLI flag (may be None).
        cli_port:  Value passed via ``--port`` CLI flag (may be None).

    Returns:
        A ``(host, port)`` tuple always containing concrete values.
    """
    # Start with env-level values
    host: str | None = cfg_host or None
    port: int | None = int(cfg_port) if cfg_port else None

    # Fall back to APP_URL only for fields not already set by env vars
    if app_url and (not host or port is None):
        # Normalize bare hosts like "myapp.com:9000" — Uri needs a scheme
        normalized = app_url if "://" in app_url else f"http://{app_url}"
        uri = Uri.of(normalized)
        if not host:
            host = uri.host() or None
        if port is None:
            port = uri.port()

    # Apply hardcoded defaults last
    host = host or "127.0.0.1"
    port = port if port is not None else 8000

    # CLI flags override everything
    if cli_host:
        host = cli_host
    if cli_port is not None:
        port = cli_port

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

        # Parse CLI flags — convert port to int if provided
        cli_host: str | None = self.option("host") or None
        cli_port: int | None = int(self.option("port")) if self.option("port") else None

        # Full priority chain: CLI arg → env var → APP_URL → hardcoded default
        host, port = _resolve_host_port(cfg_host, cfg_port, cfg_app_url, cli_host, cli_port)
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

from cleo.helpers import option
from fastapi_startkit import Config
from fastapi_startkit.console.command import Command
from fastapi_startkit.environment import env
from fastapi_startkit.support import Uriable, Uri


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

    def resolve_option(self, key: str, default: str | int | None = None):
        value = self.option(key) or Config.get(f"fastapi.{key}", default)

        return env(value)

    def resolve_url(self) -> Uriable:
        host = self.resolve_option("host", "127.0.0.1")
        port = self.resolve_option("port", 8000)

        return Uri.of(Config.get("fastapi.app_url", "http://127.0.0.1:8000")).with_host(host).with_port(port)

    def handle(self):
        import uvicorn

        from fastapi_startkit import Config
        from fastapi_startkit.container import Container

        # Resolve server settings: CLI flag > fastapi config > uvicorn default (None)
        cfg_reload_dirs = Config.get("fastapi.reload_dirs") or None
        cfg_reload_excludes = Config.get("fastapi.reload_excludes") or None

        url = self.resolve_url()

        kwargs = {
            "host": url.host(),
            "port": url.port(),
            "reload": self.resolve_option("reload", True),
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

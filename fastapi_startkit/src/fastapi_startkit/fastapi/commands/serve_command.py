import dataclasses

from cleo.helpers import option

from fastapi_startkit import Config
from fastapi_startkit.console.command import Command
from fastapi_startkit.environment import value as cast_value
from fastapi_startkit.fastapi.config import FastAPIConfig
from fastapi_startkit.support import Uri, Uriable

_CONFIG_FIELDS = {field.name: field for field in dataclasses.fields(FastAPIConfig)}


def _config_default(key: str):
    """Default declared by FastAPIConfig for *key*, or None when it declares no such field."""
    field = _CONFIG_FIELDS.get(key)

    if field is None:
        return None

    if field.default_factory is not dataclasses.MISSING:
        return field.default_factory()

    return None if field.default is dataclasses.MISSING else field.default


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
            default=None,
            description="The application to serve (overrides fastapi config)",
        ),
    ]

    def config_value(self, key: str):
        """Read ``fastapi.<key>``, falling back to the default FastAPIConfig declares for it.

        FastAPIConfig stays the single source of truth for defaults, so the command keeps
        working for applications that never registered a ``fastapi`` config of their own.
        """
        return Config.get(f"fastapi.{key}", _config_default(key))

    def resolve_option(self, key: str):
        """Resolve a server setting: CLI flag > fastapi config > FastAPIConfig default."""
        return cast_value(self.option(key) or self.config_value(key))

    def resolve_url(self) -> Uriable:
        host = self.option("host") or self.config_value("app_url")
        port = self.option("port")

        if host and not host.startswith("http"):
            host = f"http://{host}"

        uri = Uri.of(host)

        return uri.with_port(port) if port else uri

    def handle(self):
        import uvicorn

        from fastapi_startkit.container import Container

        url = self.resolve_url()
        reload = self.resolve_option("reload")
        app = self.resolve_option("app")

        kwargs = {
            "host": url.host(),
            "port": url.port(),
            "reload": reload,
            "ws": "websockets-sansio",
        }

        if self.is_app_exist(app):
            kwargs.update(
                {
                    "app": app,
                    "factory": True,
                }
            )

            if reload:
                reload_dirs = self.config_value("reload_dirs")
                reload_excludes = self.config_value("reload_excludes")

                if reload_dirs:
                    kwargs["reload_dirs"] = reload_dirs
                if reload_excludes:
                    kwargs["reload_excludes"] = reload_excludes

            self.line(f"<info>Starting Uvicorn server on {url.host()}:{url.port()} [{app}]...</info>")

        else:
            self.line(f"<info>Starting Uvicorn server on {url.host()}:{url.port()}...</info>")
            kwargs.update({"app": Container.instance().fastapi, "reload": False})

        try:
            uvicorn.run(**kwargs)
        except KeyboardInterrupt:
            self.line("<comment>Server stopped manually.</comment>")

    def is_app_exist(self, app: str) -> "bool":
        import importlib.util

        module_name = app.split(":")[0]
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                return True
        except (ImportError, ValueError):
            pass

        self.line("<fg=yellow>Unable to detect the application, run the command with --app={app}</>")

        return False

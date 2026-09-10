from pathlib import Path
from typing import Any

from cleo.helpers import option

from fastapi_startkit import Config
from fastapi_startkit.console.command import Command
from fastapi_startkit.environment import value as cast_value
from fastapi_startkit.fastapi.config import FastAPIConfig
from fastapi_startkit.support import Uri, Uriable

_GLOB_MAGIC = ("*", "?", "[")


def resolve_reload_excludes(patterns: list[str], base_path: Path | None = None) -> list[str]:
    """Rewrite directory patterns as absolute paths so uvicorn excludes them recursively.

    Uvicorn filters changed files with ``Path.match``, which is tail anchored and
    never spans more than one segment per ``*`` — so ``.claude/worktrees/*`` only
    ever matches direct children, and files nested deeper still trigger a reload.
    Uvicorn does exclude whole directory trees, but only for entries that name an
    existing directory, and the check (``exclude_dir in path.parents``) is made
    against the absolute path of the changed file, so relative entries never hit.
    """
    base = Path(base_path) if base_path else Path.cwd()

    return [str(directory) if (directory := _as_directory(pattern, base)) else pattern for pattern in patterns]


def _as_directory(pattern: str, base: Path) -> Path | None:
    """The directory a pattern points at, or None when it is a real glob."""
    candidate = pattern.rstrip("/")

    while candidate.endswith(("/*", "/**")):
        candidate = candidate.rsplit("/", 1)[0]

    if not candidate or any(magic in candidate for magic in _GLOB_MAGIC):
        return None

    path = Path(candidate)
    path = path if path.is_absolute() else base / path

    return path if path.is_dir() else None


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

    def config_value(self, key: str) -> Any:
        """Resolve `fastapi.<key>`, falling back to the FastAPIConfig default."""
        # Instantiated per call so env-backed fields are read at command time.
        default = getattr(FastAPIConfig(), key, None)
        # Configuration.get() only substitutes its default on a missing key, so a
        # key that is present but None would otherwise leak through.
        value = Config.get(f"fastapi.{key}", default)

        return default if value is None else value

    def resolve_option(self, key: str) -> Any:
        """CLI flag > fastapi config > FastAPIConfig default."""
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
                    kwargs["reload_excludes"] = resolve_reload_excludes(reload_excludes)

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

        self.line(f"<fg=yellow>Unable to detect the application '{app}', run the command with --app=your_module:app</>")

        return False

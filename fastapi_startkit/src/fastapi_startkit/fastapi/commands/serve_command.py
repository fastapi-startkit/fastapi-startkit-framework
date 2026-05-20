from fastapi_startkit.console.command import Command
from cleo.helpers import option


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

        # Resolve server settings: CLI flag > fastapi config > uvicorn default (None)
        cfg_host = Config.get("fastapi.host", "127.0.0.1")
        cfg_port = Config.get("fastapi.port", 8000)
        cfg_reload = Config.get("fastapi.reload", True)
        cfg_reload_dirs = Config.get("fastapi.reload_dirs") or None
        cfg_reload_excludes = Config.get("fastapi.reload_excludes") or None

        host = self.option("host") or cfg_host
        port = int(self.option("port") or cfg_port)
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

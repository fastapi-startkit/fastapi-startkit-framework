import os
import shlex
from fastapi_startkit.providers.app_provider import AppProvider
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from typing import Type, Callable, Any, List, TypeVar, Generic

from .config import AppConfig
from .configuration.providers import ConfigurationProvider
from .container import Container
from .environment.environment import Environment

if TYPE_CHECKING:
    from fastapi import FastAPI, APIRouter
    from starlette.middleware.base import BaseHTTPMiddleware

from fastapi_startkit.exceptions import ExceptionHandler


def app() -> "Container":
    return Container.instance()


TConfig = TypeVar("TConfig", bound=AppConfig)


class Application(Container, Generic[TConfig]):
    DEFAULT_PROVIDERS = [
        ConfigurationProvider,
        AppProvider,
    ]

    def __init__(
        self,
        base_path: str | Path = None,
        env=None,
        providers=None,
        config: Type[TConfig] | None = None,
        exception_handler: Type[ExceptionHandler] | None = None,
    ):
        super().__init__()

        self.base_path: Path = Path(base_path) if base_path else Path(os.getcwd())
        self.env = env
        self.providers = self.DEFAULT_PROVIDERS + (providers or [])
        self.published_resources = {}
        self.commands = []
        self._config = config
        self._config_instance: Optional[TConfig] = None
        self._exception_handler_class = exception_handler or ExceptionHandler
        self.exception_manager: ExceptionHandler

        # Set global singleton
        Container.set_instance(self)

        self.configure_exception_handler()

        # Boot application
        self.resolve_environment()
        self.configure_config()
        self.configure_paths()
        self.register_providers()

        self._fastapi: Optional["FastAPI"] = None
        self.load_providers()

    def set_environment(self, env: str):
        self.env = env
        return self

    def load_environment(self):
        """Reload environment variables for the current self.env."""
        Environment.load_base(base_path=self.base_path)
        Environment.load(self.env, base_path=self.base_path)
        return self

    def configure_exception_handler(self):
        self.exception_manager: ExceptionHandler = self._exception_handler_class(application=self)
        self.exception_manager.register()
        self.exception_manager.install()
        self.bind("exception_manager", self.exception_manager)

    def register_providers(self):
        providers = []
        for provider_data in self.providers:
            config = {}
            if isinstance(provider_data, tuple):
                provider_class, config = provider_data

                if callable(config):
                    config = config()
            else:
                provider_class = provider_data

            provider = provider_class(self, config=config)
            provider.register()
            providers.append(provider)

        self.providers = providers
        return self

    def load_providers(self):
        for provider in self.providers:
            self.resolve(provider.boot)
        return self

    def use_fastapi(self, fastapi: "FastAPI"):
        self._fastapi = fastapi
        return self

    def use_base_path(self, path: str):
        return self.base_path / path

    def storage_path(self, path: str = "") -> str:
        return str(self.base_path / "storage" / path)

    def public_path(self, path: str = "") -> str:
        return str(self.base_path / "public" / path)

    def get(self, path: str, **kwargs) -> Callable:
        return self.fastapi.get(path, **kwargs)

    def post(self, path: str, **kwargs) -> Callable:
        return self.fastapi.post(path, **kwargs)

    def put(self, path: str, **kwargs) -> Callable:
        return self.fastapi.put(path, **kwargs)

    def delete(self, path: str, **kwargs) -> Callable:
        return self.fastapi.delete(path, **kwargs)

    def patch(self, path: str, **kwargs) -> Callable:
        return self.fastapi.patch(path, **kwargs)

    def options(self, path: str, **kwargs) -> Callable:
        return self.fastapi.options(path, **kwargs)

    def head(self, path: str, **kwargs) -> Callable:
        return self._fastapi.head(path, **kwargs)

    def trace(self, path: str, **kwargs) -> Callable:
        return self._fastapi.trace(path, **kwargs)

    # Include routers
    def include_router(self, router: "APIRouter", **kwargs):
        self.fastapi.include_router(router, **kwargs)
        return self

    # Add middleware
    def add_middleware(self, middleware_class: Type["BaseHTTPMiddleware"], **options):
        self._fastapi.add_middleware(middleware_class, **options)
        return self

    # Add event handlers (startup/shutdown)
    def add_event_handler(self, event_type: str, func: Callable[..., Any]):
        self.fastapi.add_event_handler(event_type, func)
        return self

    # Mount sub-apps
    def mount(self, path: str, app_instance: "FastAPI", **kwargs):
        self._fastapi.mount(path, app_instance, **kwargs)
        return self

    # Add custom exception handlers
    def add_exception_handler(self, exc_class_or_status_code: Any, handler: Callable[..., Any]):
        self._fastapi.add_exception_handler(exc_class_or_status_code, handler)
        return self

    @property
    def fastapi(self) -> "FastAPI":
        if self._fastapi is None:
            try:
                from fastapi import FastAPI
            except ImportError:
                raise RuntimeError("FastAPI is not installed. Install it with: pip install fastapi")
            self._fastapi = FastAPI()
        # Making the type hint work
        assert self._fastapi is not None
        return self._fastapi

    def __call__(self, *args, **kwargs):
        return self.fastapi

    def resolve_environment(self):
        self.env = Environment.resolve_environment(base_path=self.base_path, env=self.env)
        Environment.load_base(base_path=self.base_path)
        Environment.load(self.env, base_path=self.base_path)

    def is_debug(self) -> bool:
        return (
            hasattr(self, "_config_instance")
            and self._config_instance is not None
            and getattr(self._config_instance, "debug", False)
        )

    def is_testing(self) -> bool:
        return self.env == "testing"

    def configure_config(self):
        if self._config is not None:
            self._config_instance = self._config()

    @property
    def config(self) -> TConfig:
        if self._config_instance is None:
            raise RuntimeError("Config is not set")
        return self._config_instance

    def configure_paths(self):
        self.bind("config.location", self.base_path / "config")

    def use_config_path(self, path: str = None):
        self.bind("config.location", path)

        return self

    def use_storage_path(self, path: str = None):
        self.bind("storage.location", path)

        return self

    def add_commands(self, commands: List):
        self.commands.extend(commands)

    def handle_command(self):
        from fastapi_startkit.console import ConsoleApplication

        ConsoleApplication(self).handle()

    def run(self, command: str, args: "str | list[str] | None" = None) -> int:
        from cleo.io.inputs.string_input import StringInput

        from fastapi_startkit.console import ConsoleApplication

        if isinstance(args, (list, tuple)):
            args = shlex.join(str(arg) for arg in args)

        command_line = f"{command} {args}".strip() if args else command

        console = ConsoleApplication(self)
        console.auto_exits(False)

        console.find(command)

        return console.run(StringInput(command_line))

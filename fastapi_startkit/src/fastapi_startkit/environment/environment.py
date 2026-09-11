"""Module for the LoadEnvironment class."""

import os
import sys
from typing import Any, Literal, TypeVar, overload

from dotenv import load_dotenv


T = TypeVar("T")
EnvValue = str | int | bool


_UNSET = object()


class Environment:
    @staticmethod
    def resolve_environment(base_path=None, env: str | None = None):
        Environment.resolve_environment_from_argument()

        if "PYTEST_CURRENT_TEST" in os.environ:
            return "testing"

        # Explicit env parameter takes priority over os.environ APP_ENV
        if env:
            return env

        if os.environ.get("APP_ENV"):
            return os.environ["APP_ENV"]

        path = base_path / ".env"
        if not path.exists():
            raise ValueError("Unable to determine environment.")

        load_dotenv(path, override=True)

        env = os.environ.get("APP_ENV")
        if not env:
            raise ValueError("APP_ENV not set after loading .env")

        return env

    @staticmethod
    def load_base(base_path=None):
        """Load the base .env file, resetting vars to their default values."""
        path = base_path / ".env"
        if path.exists():
            load_dotenv(path, override=True)

    @staticmethod
    def load(env: str, override=True, only=None, base_path=None):
        path = base_path / f".env.{env}"
        if not path.exists():
            return
        load_dotenv(path, override=override)

    @staticmethod
    def resolve_environment_from_argument():
        """Parse --env=<value> or --env <value> from sys.argv, set APP_ENV,
        and remove the tokens so downstream CLI parsers (e.g. cleo) never see them."""
        args = sys.argv[1:]
        for i, arg in enumerate(args):
            if arg.startswith("--env="):
                os.environ["APP_ENV"] = arg.split("=", 1)[1]
                sys.argv.pop(i + 1)
                break
            if arg == "--env" and i + 1 < len(args):
                os.environ["APP_ENV"] = args[i + 1]
                sys.argv.pop(i + 2)  # value first (higher index)
                sys.argv.pop(i + 1)  # then the flag
                break


@overload
def env(value: str, default: T, cast: Literal[False]) -> str | T: ...


@overload
def env(value: str, default: None, cast: Literal[True] = True) -> EnvValue | None: ...


@overload
def env(value: str, default: T, cast: Literal[True] = True) -> T: ...


@overload
def env(value: str, default: None, cast: bool) -> EnvValue | None: ...


@overload
def env(value: str, default: T, cast: bool) -> EnvValue | T: ...


@overload
def env(value: str) -> EnvValue: ...


@overload
def env(value: str, *, cast: Literal[False]) -> str: ...


@overload
def env(value: str, *, cast: bool) -> EnvValue: ...


def env(value: str, default: Any = _UNSET, cast: bool = True) -> Any:
    """Return an environment value, casting it to the supplied default's type when possible."""
    default_was_supplied = default is not _UNSET
    resolved_default = "" if not default_was_supplied else default
    env_var = os.getenv(value, resolved_default)

    if not cast:
        return env_var

    if env_var == "":
        env_var = resolved_default

    if not default_was_supplied or resolved_default is None:
        return _cast_value(env_var)

    default_type = type(resolved_default)
    if default_type is bool:
        if isinstance(env_var, bool):
            return env_var
        if env_var in ("true", "True"):
            return True
        if env_var in ("false", "False"):
            return False
        raise ValueError(f"Cannot cast environment variable {value!r} to bool")

    try:
        return default_type(env_var)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Cannot cast environment variable {value!r} to {default_type.__name__}") from error


def _cast_value(env_var, default=""):
    if env_var == "":
        env_var = default

    if isinstance(env_var, bool):
        return env_var
    elif env_var is None:
        return None
    elif isinstance(env_var, int) or (isinstance(env_var, str) and env_var.isnumeric()):
        return int(env_var)
    elif env_var in ("false", "False"):
        return False
    elif env_var in ("true", "True"):
        return True
    else:
        return env_var


def value(env_var, default=""):
    return _cast_value(env_var, default)

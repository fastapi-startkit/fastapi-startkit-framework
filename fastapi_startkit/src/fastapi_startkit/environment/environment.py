"""Module for the LoadEnvironment class."""

import os
import sys
from collections.abc import Callable
from dataclasses import Field, MISSING, field
from pathlib import Path
import typing
from typing import Literal, TypeVar, overload

from dotenv import load_dotenv


T = TypeVar("T")
U = TypeVar("U")
EnvValue = str | int | bool
_UNSET = object()
_BOOLEANS: dict[str, bool] = {"true": True, "True": True, "false": False, "False": False}


class Environment:
    @staticmethod
    def resolve_environment(base_path: Path | None = None, env: str | None = None):
        Environment.resolve_environment_from_argument()

        if "PYTEST_CURRENT_TEST" in os.environ:
            return "testing"

        # Explicit env parameter takes priority over os.environ APP_ENV
        if env:
            return env

        if os.environ.get("APP_ENV"):
            return os.environ["APP_ENV"]

        path = Environment._require_base_path(base_path) / ".env"
        if not path.exists():
            raise ValueError("Unable to determine environment.")

        _ = load_dotenv(path, override=True)

        env = os.environ.get("APP_ENV")
        if not env:
            raise ValueError("APP_ENV not set after loading .env")

        return env

    @staticmethod
    def _require_base_path(base_path: Path | None) -> Path:
        # Keeps the TypeError the old unguarded `None / ".env"` raised, with a clearer message.
        if base_path is None:
            raise TypeError("base_path is required to locate .env files")
        return base_path

    @staticmethod
    def load_base(base_path: Path | None = None):
        """Load the base .env file, resetting vars to their default values."""
        path = Environment._require_base_path(base_path) / ".env"
        if path.exists():
            _ = load_dotenv(path, override=True)

    @staticmethod
    def load(env: str, override: bool = True, base_path: Path | None = None):
        path = Environment._require_base_path(base_path) / f".env.{env}"
        if not path.exists():
            return
        _ = load_dotenv(path, override=override)

    @staticmethod
    def resolve_environment_from_argument():
        """Parse --env=<value> or --env <value> from sys.argv, set APP_ENV,
        and remove the tokens so downstream CLI parsers (e.g. cleo) never see them."""
        args = sys.argv[1:]
        for i, arg in enumerate(args):
            if arg.startswith("--env="):
                os.environ["APP_ENV"] = arg.split("=", 1)[1]
                del sys.argv[i + 1]
                break
            if arg == "--env" and i + 1 < len(args):
                os.environ["APP_ENV"] = args[i + 1]
                del sys.argv[i + 1 : i + 3]
                break


@overload
def env(val: str, *, cast: Literal[True] = True) -> EnvValue: ...


@overload
def env(val: str, default: None, cast: Literal[True] = True) -> EnvValue | None: ...


@overload
def env(val: str, default: T, cast: Literal[True] = True) -> T: ...


@overload
def env(val: str, *, cast: Literal[False]) -> str: ...


@overload
def env(val: str, default: T, cast: Literal[False]) -> str | T: ...


@overload
def env(val: str, *, cast: bool) -> EnvValue: ...


@overload
def env(val: str, default: None, cast: bool) -> EnvValue | None: ...


@overload
def env(val: str, default: T, cast: bool) -> str | T: ...


def env(val: str, default: object = _UNSET, cast: bool = True) -> object:
    def read() -> object:
        env_var = os.getenv(val, "" if default is _UNSET else default)

        try:
            return into(env_var, default, cast)
        except ValueError as error:
            raise ValueError(f"Cannot cast environment variable {val!r} to {type(default).__name__}") from error

    return field(default_factory=read)


def value(item: T) -> T:
    if isinstance(item, Field):
        declared = typing.cast(Field[T], item)
        if declared.default_factory is not MISSING:
            return declared.default_factory()
    return item


@overload
def into(item: bool) -> bool: ...


@overload
def into(item: int) -> int: ...


@overload
def into(item: None) -> None: ...


@overload
def into(item: str) -> EnvValue: ...


@overload
def into(item: object, default: None) -> EnvValue | None: ...


@overload
def into(item: object, default: T) -> T: ...


@overload
def into(item: U, *, cast: Literal[False]) -> U: ...


@overload
def into(item: U, default: T, cast: Literal[False]) -> U | T: ...


@overload
def into(item: U, *, cast: bool) -> U | EnvValue: ...


@overload
def into(item: U, default: None, cast: bool) -> U | EnvValue | None: ...


@overload
def into(item: U, default: T, cast: bool) -> U | T: ...


def into(item: object, default: object = _UNSET, cast: bool = True) -> object:
    if not cast:
        return default if item is None and default is not _UNSET else item

    if item is None or item == "":
        return item if default is _UNSET else default

    if isinstance(item, bool):
        return item

    if default is _UNSET or default is None:
        if isinstance(item, int) or (isinstance(item, str) and item.isnumeric()):
            return int(item)
        return _BOOLEANS.get(item, item) if isinstance(item, str) else item

    if isinstance(default, bool):
        if isinstance(item, str) and item in _BOOLEANS:
            return _BOOLEANS[item]
        raise ValueError(f"Cannot cast {item!r} to bool")

    convert = typing.cast(Callable[[object], object], type(default))
    try:
        return convert(item)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Cannot cast {item!r} to {type(default).__name__}") from error

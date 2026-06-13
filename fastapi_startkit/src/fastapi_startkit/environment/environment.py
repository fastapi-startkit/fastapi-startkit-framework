"""Module for the LoadEnvironment class."""

import os
import sys
from dotenv import load_dotenv


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


def env(value, default="", cast=True):
    """Helper to retrieve the value of an environment variable or returns
    a default value. In addition, if type can be inferred then the value can be casted to the
    inferred type."""
    env_var = os.getenv(value, default)

    if not cast:
        return env_var

    if env_var == "":
        env_var = default

    if isinstance(env_var, bool):
        return env_var
    elif env_var is None:
        return None
    elif isinstance(env_var, int) or env_var.isnumeric():
        return int(env_var)
    elif env_var in ("false", "False"):
        return False
    elif env_var in ("true", "True"):
        return True
    else:
        return env_var


def value(env_var, default=""):
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

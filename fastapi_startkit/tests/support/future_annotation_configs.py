from __future__ import annotations

import typing
from dataclasses import InitVar
from typing import ClassVar

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


class FutureRegistry(Config):
    registry: ClassVar[dict[str, int]] = {}
    aliases: typing.ClassVar[list[str]] = []
    seed: InitVar[int] = 0
    driver: str = "memory"


class FutureEnvRegistry(Config):
    registry: ClassVar[dict[str, int]] = {}
    host: str = env("FUTURE_CLASSVAR_HOST", "localhost")

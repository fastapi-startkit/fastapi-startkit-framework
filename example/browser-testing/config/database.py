from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm.config.config import SQLiteConfig
from fastapi_startkit.masoniteorm.config.database import DatabaseConfig as BaseDatabaseConfig


@dataclass
class DatabaseConfig(BaseDatabaseConfig):
    default: str = env("DB_CONNECTION", "sqlite")
    connections: dict = field(default_factory=lambda: {"sqlite": SQLiteConfig()})

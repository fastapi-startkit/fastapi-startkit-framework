from fastapi_startkit.config import AppConfig as BaseConfig
from dataclasses import dataclass, field

from config.database import DatabaseConfig


@dataclass
class AppConfig(BaseConfig):
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

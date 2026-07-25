from fastapi_startkit.config import AppConfig as BaseConfig
from pydantic.dataclasses import dataclass

from config.database import DatabaseConfig
from dataclasses import field


@dataclass
class AppConfig(BaseConfig):
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

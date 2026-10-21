from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class ArrayStoreConfig(Config):
    driver: str = "array"


@dataclass
class FileStoreConfig(Config):
    driver: str = "file"
    path: str = env("CACHE_FILE_PATH", "storage/framework/cache/data")


@dataclass
class DatabaseStoreConfig(Config):
    driver: str = "database"
    connection: str | None = env("DB_CACHE_CONNECTION", None, cast=False)
    table: str = env("DB_CACHE_TABLE", "caches")


@dataclass
class CacheConfig(Config):
    default: str = env("CACHE_CONNECTION", "file")
    prefix: str = env("CACHE_PREFIX", "cache")
    stores: dict[str, Config] = field(
        default_factory=lambda: {
            "array": ArrayStoreConfig(),
            "file": FileStoreConfig(),
            "database": DatabaseStoreConfig(),
        }
    )


__all__ = ["ArrayStoreConfig", "CacheConfig", "DatabaseStoreConfig", "FileStoreConfig"]

from dataclasses import field
from typing import Any

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import PostgresConfig
from pydantic.dataclasses import dataclass


@dataclass
class DatabaseConfig:
    default: str = field(default_factory=lambda: env("DB_CONNECTION", "postgres"))

    connections: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            # Same Postgres instance the LangGraph checkpointer uses, so a thread row
            # here lines up with the checkpointer's thread_id.
            "postgres": PostgresConfig(
                driver="postgres",
                host=env("DB_HOST", "localhost"),
                port=env("DB_PORT", 5432),
                database=env("DB_DATABASE", "agents"),
                username=env("DB_USERNAME", "postgres"),
                password=env("DB_PASSWORD", "postgres"),
                sslmode=env("DB_SSLMODE", "disable"),
            ),
        }
    )

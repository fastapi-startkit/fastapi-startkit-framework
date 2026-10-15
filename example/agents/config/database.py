from dataclasses import dataclass, field

from fastapi_startkit.environment import env, value
from fastapi_startkit.masoniteorm import DatabaseConfig as BaseDatabaseConfig
from fastapi_startkit.masoniteorm import DBConfig, PostgresConfig


@dataclass
class DatabaseConfig(BaseDatabaseConfig):
    default: str = env("DB_CONNECTION", "postgres")

    connections: dict[str, DBConfig] = field(
        default_factory=lambda: {
            # Same Postgres instance the LangGraph checkpointer uses, so a thread row
            # here lines up with the checkpointer's thread_id.
            "postgres": PostgresConfig(
                driver="postgres",
                host=value(env("DB_HOST", "localhost")),
                port=value(env("DB_PORT", 5432)),
                database=value(env("DB_DATABASE", "agents")),
                username=value(env("DB_USERNAME", "postgres")),
                password=value(env("DB_PASSWORD", "postgres")),
                sslmode=value(env("DB_SSLMODE", "disable")),
            ),
        }
    )

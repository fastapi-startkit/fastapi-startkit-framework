from fastapi_startkit.masoniteorm import DatabaseConfig, PostgresConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager

import os

_port = os.getenv("POSTGRES_PORT", "5432")
URL = f"postgresql+asyncpg://app:secret@localhost:{_port}/database_app_test"

DB = DatabaseManager(
    ConnectionFactory(),
    DatabaseConfig(
        default="postgres",
        connections={
            "postgres": PostgresConfig(driver="postgres", url=URL, database="database_app_test"),
            "dev": PostgresConfig(driver="postgres", url=URL, database="database_app_test"),
        },
    ),
)

schema = DB.get_schema_builder()

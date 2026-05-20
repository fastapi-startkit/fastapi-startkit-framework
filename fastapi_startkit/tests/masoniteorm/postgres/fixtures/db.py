from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager

import os

_port = os.getenv("POSTGRES_PORT", "5432")
URL = f"postgresql+asyncpg://app:secret@localhost:{_port}/database_app_test"

DB = DatabaseManager(
    ConnectionFactory(),
    {
        "default": "postgres",
        "connections": {
            "postgres": {
                "driver": "postgres",
                "url": URL,
                "database": "database_app_test",
            },
            "dev": {
                "driver": "postgres",
                "url": URL,
                "database": "database_app_test",
            },
        },
    },
)

schema = DB.get_schema_builder()

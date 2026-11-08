import os

from fastapi_startkit.masoniteorm import DatabaseConfig, MySQLConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.model import Model

_port = os.getenv("MYSQL_PORT", "3306")
URL = f"mysql+aiomysql://app:secret@127.0.0.1:{_port}/database_app_test"

DB = DatabaseManager(
    ConnectionFactory(),
    DatabaseConfig(
        default="mysql",
        connections={"mysql": MySQLConfig(driver="mysql", url=URL)},
    ),
)

Model.db_manager = DB

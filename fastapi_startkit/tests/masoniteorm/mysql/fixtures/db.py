from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.models.model import Model

DB = DatabaseManager(
    ConnectionFactory(),
    {
        "default": "mysql",
        "connections": {
            "mysql": {
                "driver": "mysql",
                "url": "mysql+aiomysql://root:@localhost:3306/test",
            },
        },
    },
)

Model.db_manager = DB

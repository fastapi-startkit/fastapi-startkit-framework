import pytest
from sqlalchemy import StaticPool, text

from fastapi_startkit.application import Application
from fastapi_startkit.masoniteorm import DatabaseConfig, MySQLConfig, PostgresConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.connections.mysql_connection import MySQLConnection
from fastapi_startkit.masoniteorm.connections.postgres_connection import PostgresConnection
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.providers.DatabaseProvider import DatabaseProvider


@pytest.mark.parametrize(
    "config_type,driver,expected_url",
    [
        (SQLiteConfig, "sqlite", "sqlite+aiosqlite:///test.db"),
        (MySQLConfig, "mysql", "mysql+aiomysql://user:secret@localhost:3306/test.db"),
        (PostgresConfig, "postgres", "postgresql+asyncpg://user:secret@localhost:5432/test.db"),
    ],
)
def test_config_builds_its_url(config_type, driver, expected_url):
    values = {"driver": driver, "database": "test.db", "url": None}
    if driver != "sqlite":
        values.update(host="localhost", username="user", password="secret", port=3306 if driver == "mysql" else 5432)
    assert config_type(**values).build_url() == expected_url


def test_config_uses_explicit_url():
    config = MySQLConfig(url="mysql+aiomysql://custom:secret@db:3307/app")
    assert config.build_url() == config.url


def test_engine_options():
    assert SQLiteConfig().engine_options() == {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    assert MySQLConfig().engine_options() == {}
    assert PostgresConfig().engine_options() == {}


@pytest.mark.parametrize(
    "config,connection_type",
    [
        (SQLiteConfig(database=":memory:", url=None), SQliteConnection),
        (MySQLConfig(url="mysql+aiomysql://user:secret@localhost:3306/app"), MySQLConnection),
        (PostgresConfig(url="postgresql+asyncpg://user:secret@localhost:5432/app"), PostgresConnection),
    ],
)
def test_factory_creates_matching_connection(config, connection_type):
    connection = ConnectionFactory().make(config, config.driver)
    assert isinstance(connection, connection_type)
    assert connection.config is config


async def test_manager_accepts_config_object():
    config = SQLiteConfig(database=":memory:", url=None)
    manager = DatabaseManager(ConnectionFactory(), DatabaseConfig(default="sqlite", connections={"sqlite": config}))
    connection = manager.connection()
    try:
        assert connection.config is config
        assert connection.config.database == ":memory:"
        async with connection.engine.connect() as db:
            assert (await db.execute(text("select 1"))).scalar() == 1
    finally:
        await manager.clear()


def test_connection_rejects_mismatched_driver():
    with pytest.raises(ValueError, match="does not match"):
        ConnectionFactory.create_connection("mysql", SQLiteConfig())


def test_provider_rejects_dictionary_connection_settings(tmp_path):
    app = Application(base_path=tmp_path)
    config = DatabaseConfig(default="sqlite", connections={"sqlite": {"driver": "sqlite"}})
    with pytest.raises(TypeError, match="Database connection 'sqlite' requires a database config object"):
        DatabaseProvider(app, config).register()

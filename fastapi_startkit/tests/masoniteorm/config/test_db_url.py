import pytest

from fastapi_startkit.exceptions.exceptions import DriverNotFound
from fastapi_startkit.masoniteorm import MySQLConfig, PostgresConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory


@pytest.mark.parametrize(
    "config,expected",
    [
        (
            MySQLConfig(host="localhost", port=3306, database="mydb", username="root", password="secret", url=None),
            "mysql+aiomysql://root:secret@localhost:3306/mydb",
        ),
        (
            PostgresConfig(
                host="db.example.com", port=5432, database="mydb", username="user", password="pass", url=None
            ),
            "postgresql+asyncpg://user:pass@db.example.com:5432/mydb",
        ),
        (SQLiteConfig(database="database.sqlite", url=None), "sqlite+aiosqlite:///database.sqlite"),
        (SQLiteConfig(database="/var/data/database.sqlite", url=None), "sqlite+aiosqlite:////var/data/database.sqlite"),
        (SQLiteConfig(url="sqlite+aiosqlite:///db.sqlite3"), "sqlite+aiosqlite:///db.sqlite3"),
        (
            MySQLConfig(url="mysql+aiomysql://admin:pw@prod-host:3306/live", host="ignored"),
            "mysql+aiomysql://admin:pw@prod-host:3306/live",
        ),
        (
            PostgresConfig(host="localhost", port=6543, database="mydb", username="user", password="pass", url=None),
            "postgresql+asyncpg://user:pass@localhost:6543/mydb",
        ),
    ],
)
def test_build_url(config, expected):
    assert ConnectionFactory.build_url(config) == expected


@pytest.mark.parametrize("config_type,port", [(MySQLConfig, 3306), (PostgresConfig, 5432)])
def test_default_port(config_type, port):
    config = config_type(host="localhost", database="app", username="user", password="secret", url=None)
    assert f"localhost:{port}/app" in ConnectionFactory.build_url(config)


@pytest.mark.parametrize("driver", ["oracle", "cassandra"])
def test_unknown_driver_raises_driver_not_found(driver):
    config = SQLiteConfig(driver=driver, url=None)
    with pytest.raises(DriverNotFound, match=driver):
        ConnectionFactory.build_url(config)
    with pytest.raises(DriverNotFound, match=driver):
        ConnectionFactory().make(config, driver)


@pytest.mark.parametrize("echo", [False, True])
def test_engine_echo(echo):
    engine = ConnectionFactory.create_engine(SQLiteConfig(database=":memory:", url=None, echo=echo))
    assert engine.echo is echo


@pytest.mark.parametrize("config_type", [SQLiteConfig, MySQLConfig, PostgresConfig])
def test_echo_defaults_to_false(config_type, monkeypatch):
    monkeypatch.delenv("DB_ECHO", raising=False)
    assert config_type().echo is False

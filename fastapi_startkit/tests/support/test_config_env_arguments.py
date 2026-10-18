from dataclasses import dataclass

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DatabaseConfig


@dataclass
class ServiceConfig(Config):
    host: str = "localhost"
    port: int = 80


def test_env_keyword_argument_is_resolved(monkeypatch):
    monkeypatch.setenv("SERVICE_HOST", "example.test")
    assert ServiceConfig(host=env("SERVICE_HOST", "localhost")).host == "example.test"


def test_env_positional_argument_is_resolved(monkeypatch):
    monkeypatch.setenv("SERVICE_PORT", "8080")
    config = ServiceConfig("example.test", env("SERVICE_PORT", 80))
    assert config.port == 8080


def test_plain_arguments_are_unchanged():
    assert ServiceConfig("example.test", 81) == ServiceConfig(host="example.test", port=81)


def test_default_sqlite_connection_reads_database_path(monkeypatch):
    monkeypatch.setenv("DB_DATABASE", "databases/custom.db")
    assert DatabaseConfig().connections["sqlite"].build_url() == "sqlite+aiosqlite:///databases/custom.db"

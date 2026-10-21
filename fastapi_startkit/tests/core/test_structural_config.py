import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import assert_type

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DatabaseConfig, DBConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.providers.DatabaseProvider import DatabaseProvider


@dataclass
class PlainAppConfig:
    name: str = "plain"
    env: str = "testing"
    debug: bool = False
    timezone: str = "UTC"
    region: str = "eu"


@dataclass
class PlainDatabaseConfig:
    default: str = "sqlite"
    connections: dict[str, DBConfig] = field(
        default_factory=lambda: {"sqlite": SQLiteConfig(url="sqlite+aiosqlite:///:memory:")}
    )
    pool: int = 5


@dataclass
class SubclassedDatabaseConfig(DatabaseConfig):
    default: str = env("STRUCTURAL_DB_CONNECTION", "sqlite")


@dataclass
class OnlyDefault:
    default: str = "sqlite"


def boot(tmp_path: Path, settings: object) -> Application[PlainAppConfig]:
    return Application(
        base_path=tmp_path, env="testing", config=PlainAppConfig, providers=[(DatabaseProvider, settings)]
    )


def test_plain_app_config_is_used_as_is(tmp_path: Path):
    app = boot(tmp_path, PlainDatabaseConfig())

    assert_type(app.config, PlainAppConfig)
    assert isinstance(app.config, PlainAppConfig)
    assert app.config.region == "eu"
    assert app.is_debug() is False


def test_plain_database_config_with_extra_field_is_the_same_object(tmp_path: Path):
    settings = PlainDatabaseConfig()

    app = boot(tmp_path, settings)

    assert app.make("db").config is settings
    assert app.make("db").connection().config is settings.connections["sqlite"]
    assert app.make("config").get("database.pool") == 5
    assert app.make("config").get("database.migrations") == DatabaseConfig().migrations


def test_database_manager_accepts_plain_database_config():
    settings = PlainDatabaseConfig()

    manager = DatabaseManager(ConnectionFactory(), settings)

    assert manager.config is settings
    assert manager.get_default_connection_name(None) == "sqlite"


def test_subclassed_database_config_keeps_its_behaviour(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STRUCTURAL_DB_CONNECTION", "memory")
    settings = SubclassedDatabaseConfig(
        default=env("STRUCTURAL_DB_CONNECTION", "sqlite"),
        connections={"memory": SQLiteConfig(url="sqlite+aiosqlite:///:memory:")},
    )

    app = boot(tmp_path, settings)

    assert settings.default == "memory"
    assert app.make("db").config is settings
    assert set(SubclassedDatabaseConfig.connections) == {"sqlite"}


def test_wrong_shape_names_the_missing_attributes(tmp_path: Path):
    with pytest.raises(
        TypeError, match="DatabaseProvider requires database settings; missing attributes: connections$"
    ):
        boot(tmp_path, OnlyDefault())


@pytest.mark.skipif(shutil.which("basedpyright") is None, reason="basedpyright is not installed")
def test_basedpyright_accepts_plain_dataclasses(tmp_path: Path):
    snippet = tmp_path / "snippet.py"
    snippet.write_text(Path(__file__).read_text())
    result = subprocess.run(
        ["basedpyright", "--level", "error", "--pythonpath", sys.executable, str(snippet)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout

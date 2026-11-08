import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import assert_type

import pytest

from fastapi_startkit.application import Application, AppSettings
from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DatabaseConfig, DBConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.config.database import DatabaseSettings
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.providers.DatabaseProvider import DatabaseProvider
from fastapi_startkit.support.config import ensure_config


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
    migrations: dict[str, str] = field(
        default_factory=lambda: {"table": "schema_migrations", "directory": "db/migrations"}
    )


@dataclass
class WithoutMigrations:
    default: str = "sqlite"
    connections: dict[str, DBConfig] = field(default_factory=lambda: {"sqlite": SQLiteConfig()})


@dataclass
class SubclassedDatabaseConfig(DatabaseConfig):
    default: str = env("STRUCTURAL_DB_CONNECTION", "sqlite")


@dataclass
class OnlyDefault:
    default: str = "sqlite"


def boot(tmp_path: Path, settings: object) -> Application[PlainAppConfig]:
    return Application(base_path=tmp_path, config=PlainAppConfig, providers=[(DatabaseProvider, settings)])


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
    assert app.make("config").get("database.migrations") == {
        "table": "schema_migrations",
        "directory": "db/migrations",
    }


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
    assert set(SubclassedDatabaseConfig.connections) == {"sqlite", "mysql", "postgres"}


def test_wrong_shape_names_the_missing_attributes(tmp_path: Path):
    with pytest.raises(
        TypeError, match="DatabaseProvider requires DatabaseSettings; missing attributes: connections, migrations$"
    ):
        boot(tmp_path, OnlyDefault())


def test_database_settings_requires_migrations(tmp_path: Path):
    assert not isinstance(WithoutMigrations(), DatabaseSettings)
    with pytest.raises(TypeError, match="DatabaseProvider requires DatabaseSettings; missing attributes: migrations$"):
        boot(tmp_path, WithoutMigrations())


def test_subclassed_database_config_keeps_default_migrations(tmp_path: Path):
    app = boot(tmp_path, SubclassedDatabaseConfig())

    assert app.make("config").get("database.migrations.table") == "migrations"
    assert app.make("config").get("database.migrations.directory") == "databases/migrations"


EXAMPLES = Path(__file__).resolve().parents[3] / "example"


def load_example_database_config(app: str) -> object:
    spec = importlib.util.spec_from_file_location(f"{app}_database_config", EXAMPLES / app / "config" / "database.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DatabaseConfig()


@pytest.mark.parametrize("app", ["agents", "browser-testing", "database-app", "inertia-pingcrm-app"])
def test_example_database_configs_satisfy_database_settings(app: str):
    settings = load_example_database_config(app)

    assert isinstance(settings, DatabaseSettings)
    assert isinstance(settings.migrations["directory"], str)


def test_framework_database_config_satisfies_database_settings():
    settings = DatabaseConfig()

    assert isinstance(settings, DatabaseSettings)
    assert settings.migrations == {"table": "migrations", "directory": "databases/migrations"}


def test_ensure_config_returns_database_settings_typed_as_the_protocol():
    settings = PlainDatabaseConfig()

    ensured = ensure_config("Owner", settings, DatabaseSettings)

    assert_type(ensured, DatabaseSettings)
    assert ensured is settings
    assert ensure_config("Owner", DatabaseConfig(), DatabaseSettings).migrations["directory"] == "databases/migrations"


def test_ensure_config_names_owner_protocol_and_missing_database_attributes():
    with pytest.raises(
        TypeError, match="^Owner requires DatabaseSettings; missing attributes: connections, migrations$"
    ):
        ensure_config("Owner", OnlyDefault(), DatabaseSettings)


def test_ensure_config_returns_app_settings_typed_as_the_protocol():
    settings = PlainAppConfig()

    ensured = ensure_config("Owner", settings, AppSettings)

    assert_type(ensured, AppSettings)
    assert ensured is settings


def test_ensure_config_names_missing_app_attributes():
    with pytest.raises(TypeError, match="^Owner requires AppSettings; missing attributes: name, env, debug, timezone$"):
        ensure_config("Owner", object(), AppSettings)


@pytest.mark.skipif(shutil.which("basedpyright") is None, reason="basedpyright is not installed")
def test_basedpyright_accepts_plain_dataclasses(tmp_path: Path):
    snippet = tmp_path / "snippet.py"
    snippet.write_text(Path(__file__).read_text())
    (tmp_path / "pyrightconfig.json").write_text('{"typeCheckingMode": "standard"}')
    result = subprocess.run(
        ["basedpyright", "--pythonpath", sys.executable, str(snippet)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stdout

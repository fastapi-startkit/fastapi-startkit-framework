from dataclasses import Field, dataclass

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.configuration import Config
from fastapi_startkit.configuration.config import Config as ConfigFacade
from fastapi_startkit.container.container import Container
from fastapi_startkit.environment import env


@pytest.fixture
def app(tmp_path):
    original = Container._instance
    yield Application(base_path=tmp_path, env="testing")
    Container._instance = original


class StaticAppConfig(Config):
    name: str = env("STATIC_APP_NAME", "Startkit")
    port: int = env("STATIC_APP_PORT", 8000)


@dataclass
class DecoratedStaticAppConfig(Config):
    name: str = env("STATIC_APP_NAME", "Startkit")
    port: int = env("STATIC_APP_PORT", 8000)


def test_class_level_access_without_instantiating(monkeypatch):
    class FreshAppConfig(Config):
        name: str = env("STATIC_APP_NAME", "Startkit")
        port: int = env("STATIC_APP_PORT", 8000)

    monkeypatch.delenv("STATIC_APP_NAME", raising=False)
    assert not isinstance(FreshAppConfig.name, Field)
    assert (FreshAppConfig.name, FreshAppConfig.port) == ("Startkit", 8000)
    monkeypatch.setenv("STATIC_APP_NAME", "Overridden")
    monkeypatch.setenv("STATIC_APP_PORT", "9000")
    assert (FreshAppConfig.name, FreshAppConfig.port) == ("Overridden", 9000)


@pytest.mark.parametrize("config_class", [StaticAppConfig, DecoratedStaticAppConfig])
def test_facade_reads_registered_config_instance(app, monkeypatch, config_class):
    monkeypatch.delenv("STATIC_APP_NAME", raising=False)
    monkeypatch.delenv("STATIC_APP_PORT", raising=False)
    app.make("config").set("app", config_class())
    assert (ConfigFacade.get("app.name"), ConfigFacade.get("app.port")) == ("Startkit", 8000)
    monkeypatch.setenv("STATIC_APP_NAME", "Overridden")
    monkeypatch.setenv("STATIC_APP_PORT", "9000")
    app.make("config").set("app", config_class())
    assert (ConfigFacade.get("app.name"), ConfigFacade.get("app.port")) == ("Overridden", 9000)


@pytest.mark.parametrize("config_class", [StaticAppConfig, DecoratedStaticAppConfig])
def test_facade_reads_registered_config_class(app, monkeypatch, config_class):
    monkeypatch.setenv("STATIC_APP_NAME", "Overridden")
    app.make("config").set("app", config_class)
    assert ConfigFacade.get("app.name") == "Overridden"

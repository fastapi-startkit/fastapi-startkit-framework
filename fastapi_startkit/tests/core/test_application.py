"""Tests for the Application lifecycle."""

import os

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.providers import Provider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container_instance():
    """Save and restore Container._instance around every test to prevent leakage."""
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# Stub providers used across tests
# ---------------------------------------------------------------------------


class StubProvider(Provider):
    def register(self):
        self.app.bind("stub_service", "stub_value")

    def boot(self):
        pass


# ---------------------------------------------------------------------------
# Initialisation and singleton
# ---------------------------------------------------------------------------


class TestApplicationInit:
    def test_sets_container_singleton_on_init(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        assert Container.instance() is a

    def test_second_application_replaces_singleton(self, tmp_path):
        a1 = Application(base_path=tmp_path, env="testing")
        a2 = Application(base_path=tmp_path, env="testing")
        assert Container.instance() is a2
        assert Container.instance() is not a1

    def test_base_path_stored_as_path_object(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        from pathlib import Path

        assert a.base_path == Path(tmp_path)

    def test_base_path_from_string(self, tmp_path):
        a = Application(base_path=str(tmp_path), env="testing")
        from pathlib import Path

        assert a.base_path == Path(tmp_path)

    def test_exception_manager_bound_in_container(self, app):
        assert app.has("exception_manager")

    def test_is_testing_when_env_is_testing(self, app):
        assert app.is_testing() is True


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------


class TestConfigurePaths:
    def test_config_location_is_bound(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        assert a.make("config.location") == tmp_path / "config"

    def test_use_config_path_overrides_binding(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        custom = tmp_path / "my_config"
        a.use_config_path(str(custom))
        assert a.make("config.location") == str(custom)

    def test_storage_path_appends_to_base(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        assert a.storage_path("logs") == str(tmp_path / "storage" / "logs")

    def test_storage_path_empty_returns_base_storage(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        assert a.storage_path() == str(tmp_path / "storage")

    def test_public_path_appends_to_base(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing")
        assert a.public_path("css") == str(tmp_path / "public" / "css")


# ---------------------------------------------------------------------------
# Provider two-phase lifecycle
# ---------------------------------------------------------------------------


class TestProviderLifecycle:
    def test_register_called_before_boot(self, tmp_path):
        call_log = []

        class OrderedProvider(Provider):
            def register(self):
                call_log.append("register")

            def boot(self):
                call_log.append("boot")

        Application(base_path=tmp_path, env="testing", providers=[OrderedProvider])
        assert "register" in call_log
        assert "boot" in call_log
        assert call_log.index("register") < call_log.index("boot")

    def test_all_registers_complete_before_any_boot(self, tmp_path):
        """All register() calls must finish before any boot() is invoked."""
        call_log = []

        class ProviderA(Provider):
            def register(self):
                call_log.append("register_a")

            def boot(self):
                call_log.append("boot_a")

        class ProviderB(Provider):
            def register(self):
                call_log.append("register_b")

            def boot(self):
                call_log.append("boot_b")

        Application(base_path=tmp_path, env="testing", providers=[ProviderA, ProviderB])
        register_indices = [i for i, x in enumerate(call_log) if x.startswith("register")]
        boot_indices = [i for i, x in enumerate(call_log) if x.startswith("boot")]
        assert register_indices and boot_indices
        assert max(register_indices) < min(boot_indices)

    def test_boot_can_resolve_binding_from_another_provider(self, tmp_path):
        """A provider's boot() can safely make() a binding registered by an earlier provider."""
        resolved = []

        class BindingProvider(Provider):
            def register(self):
                self.app.bind("shared_service", "hello")

        class ConsumerProvider(Provider):
            def boot(self):
                resolved.append(self.app.make("shared_service"))

        Application(base_path=tmp_path, env="testing", providers=[BindingProvider, ConsumerProvider])
        assert resolved == ["hello"]

    def test_extra_providers_appended_to_defaults(self, tmp_path):
        a = Application(base_path=tmp_path, env="testing", providers=[StubProvider])
        assert a.make("stub_service") == "stub_value"

    def test_tuple_provider_with_config_dict(self, tmp_path):
        received_config = {}

        class ConfiguredProvider(Provider):
            def register(self):
                received_config.update(self.config)

        Application(
            base_path=tmp_path,
            env="testing",
            providers=[(ConfiguredProvider, {"key": "value"})],
        )
        assert received_config == {"key": "value"}


# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------


class TestEnvironmentLoading:
    def test_env_attribute_is_set_to_testing_under_pytest(self, app):
        # PYTEST_CURRENT_TEST is always present, so env resolves to "testing"
        assert app.env == "testing"

    def test_load_environment_reads_env_file(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("APP_NAME=BaseApp\n")
        monkeypatch.delenv("APP_NAME", raising=False)

        a = Application(base_path=tmp_path, env="testing")
        a.load_environment()
        assert os.environ.get("APP_NAME") == "BaseApp"

    def test_load_environment_env_specific_overrides_base(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("APP_NAME=BaseApp\n")
        (tmp_path / ".env.testing").write_text("APP_NAME=TestingApp\n")
        monkeypatch.delenv("APP_NAME", raising=False)

        a = Application(base_path=tmp_path, env="testing")
        a.load_environment()
        assert os.environ.get("APP_NAME") == "TestingApp"

    def test_load_environment_missing_env_file_is_silent(self, tmp_path, monkeypatch):
        monkeypatch.delenv("APP_NAME", raising=False)
        # No .env or .env.testing file — should not raise
        a = Application(base_path=tmp_path, env="testing")
        a.load_environment()  # must not raise


# ---------------------------------------------------------------------------
# FastAPI lazy-loading
# ---------------------------------------------------------------------------


class TestFastapiLazyLoad:
    def test_fastapi_is_none_after_init(self, app):
        assert app._fastapi is None

    def test_fastapi_property_creates_fastapi_instance(self, app):
        from fastapi import FastAPI

        assert isinstance(app.fastapi, FastAPI)

    def test_fastapi_property_returns_same_instance_each_time(self, app):
        f1 = app.fastapi
        f2 = app.fastapi
        assert f1 is f2

    def test_use_fastapi_sets_instance(self, tmp_path):
        from fastapi import FastAPI

        a = Application(base_path=tmp_path, env="testing")
        custom = FastAPI()
        a.use_fastapi(custom)
        assert a.fastapi is custom


# ---------------------------------------------------------------------------
# App config integration
# ---------------------------------------------------------------------------


class TestAppConfig:
    def test_config_property_raises_when_no_config_class_given(self, app):
        with pytest.raises(RuntimeError, match="Config is not set"):
            _ = app.config

    def test_config_instantiated_from_class(self, tmp_path):
        from dataclasses import dataclass

        @dataclass
        class MyConfig:
            name: str = "test"

        a = Application(base_path=tmp_path, env="testing", config=MyConfig)
        assert a.config.name == "test"

    def test_is_debug_false_without_config(self, app):
        assert app.is_debug() is False

    def test_is_debug_reflects_config_value(self, tmp_path):
        from dataclasses import dataclass

        @dataclass
        class DebugConfig:
            debug: bool = True

        a = Application(base_path=tmp_path, env="testing", config=DebugConfig)
        assert a.is_debug() is True

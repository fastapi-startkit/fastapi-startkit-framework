"""Tests for the Facade layer (task #11)."""

import pytest

from fastapi_startkit.container.container import Container


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container_instance():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    from fastapi_startkit.application import Application

    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# Facade base — resolution via container
# ---------------------------------------------------------------------------


class TestFacadeBase:
    def test_facade_delegates_attribute_to_container_binding(self, app):
        """A facade's __getattr__ should delegate to the container-resolved object."""

        class FakeService:
            def greet(self):
                return "hello"

        app.bind("fake_svc", FakeService())

        from fastapi_startkit.facades.Facade import Facade

        class FakeFacade(metaclass=Facade):
            key = "fake_svc"

        assert FakeFacade.greet() == "hello"

    def test_facade_raises_when_app_not_booted(self, tmp_path):
        """Accessing a facade without a booted Application should raise."""
        # Reset the singleton so no app is active
        Container._instance = None

        from fastapi_startkit.facades.Facade import Facade

        class OrphanFacade(metaclass=Facade):
            key = "orphan_svc"

        with pytest.raises(Exception):
            _ = OrphanFacade.some_method

    def test_facade_reflects_updated_container_binding(self, app):
        """Re-binding a key should be reflected in the next facade call."""

        class V1:
            def name(self):
                return "v1"

        class V2:
            def name(self):
                return "v2"

        app.bind("versioned_svc", V1())

        from fastapi_startkit.facades.Facade import Facade

        class VersionedFacade(metaclass=Facade):
            key = "versioned_svc"

        assert VersionedFacade.name() == "v1"

        app.bind("versioned_svc", V2())
        assert VersionedFacade.name() == "v2"


# ---------------------------------------------------------------------------
# Config facade
# ---------------------------------------------------------------------------


class TestConfigFacade:
    def test_config_set_and_get(self, app):
        from fastapi_startkit.configuration.config import Config

        Config.set("app.name", "TestApp")
        assert Config.get("app.name") == "TestApp"

    def test_config_get_returns_default(self, app):
        from fastapi_startkit.configuration.config import Config

        assert Config.get("does.not.exist", "default_val") == "default_val"

    def test_config_has_existing_key(self, app):
        from fastapi_startkit.configuration.config import Config

        Config.set("feature.flag", True)
        assert Config.has("feature.flag") is True

    def test_config_has_missing_key(self, app):
        from fastapi_startkit.configuration.config import Config

        assert Config.has("absent.key") is False

    def test_config_all_returns_mapping(self, app):
        from fastapi_startkit.configuration.config import Config

        Config.set("z_key", 123)
        result = Config.all()
        # Returns a dotty-dict mapping (supports key access like a dict)
        assert result["z_key"] == 123

    def test_config_overwrite(self, app):
        from fastapi_startkit.configuration.config import Config

        Config.set("overwrite_me", "old")
        Config.set("overwrite_me", "new")
        assert Config.get("overwrite_me") == "new"

    def test_config_does_not_bleed_between_apps(self, tmp_path):
        from fastapi_startkit.application import Application
        from fastapi_startkit.configuration.config import Config

        app1 = Application(base_path=tmp_path / "app1", env="testing")
        Config.set("isolated", "from_app1")
        assert Config.get("isolated") == "from_app1"

        # Resetting singleton resets the config
        Container._instance = None
        app2 = Application(base_path=tmp_path / "app2", env="testing")
        assert Config.get("isolated") is None


# ---------------------------------------------------------------------------
# Partial spot-check: other facades exist and have correct key attribute
# ---------------------------------------------------------------------------


class TestFacadeKeyAttributes:
    def test_hash_facade_key(self):
        try:
            from fastapi_startkit.facades import Hash

            # If importable, the key attribute should be a string
            if hasattr(Hash, "key"):
                assert isinstance(Hash.key, str)
        except ImportError:
            pytest.skip("Hash facade not available")

    def test_facade_module_exports_config(self):
        from fastapi_startkit import facades

        assert hasattr(facades, "Config")

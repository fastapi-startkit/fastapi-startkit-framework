"""Tests for the Provider pattern (task #10)."""

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.providers import Provider


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
    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# Stub providers
# ---------------------------------------------------------------------------


class BindingProvider(Provider):
    """Registers a single binding."""

    def register(self):
        self.app.bind("binding_provider_service", "bound_value")


class BootAccessProvider(Provider):
    """Resolves another provider's binding in boot()."""

    resolved_in_boot = None

    def register(self):
        self.app.bind("boot_access_service", "from_boot_access")

    def boot(self):
        BootAccessProvider.resolved_in_boot = self.app.make("binding_provider_service")


class OrderTrackingProvider(Provider):
    """Appends 'register' / 'boot' events to a shared call_log."""

    call_log: list = []

    def register(self):
        OrderTrackingProvider.call_log.append(f"{self.__class__.__name__}.register")

    def boot(self):
        OrderTrackingProvider.call_log.append(f"{self.__class__.__name__}.boot")


class OrderTrackingProviderB(Provider):
    call_log: list = []

    def register(self):
        OrderTrackingProviderB.call_log.append(f"{self.__class__.__name__}.register")

    def boot(self):
        OrderTrackingProviderB.call_log.append(f"{self.__class__.__name__}.boot")


class DuplicateKeyProvider(Provider):
    """Registers the same key twice to verify last-write-wins behaviour."""

    def register(self):
        self.app.bind("dup_key", "first")
        self.app.bind("dup_key", "second")


class ConfigResolveProvider(Provider):
    """Uses resolve_config / merge_config_from helpers."""

    def register(self):
        self.app.bind("cfg_service", {"default": True})

    def boot(self):
        pass


# ---------------------------------------------------------------------------
# Provider key inference
# ---------------------------------------------------------------------------


class TestProviderKey:
    def test_provider_key_inferred_from_class_name(self, app):
        class MyServiceProvider(Provider):
            pass

        p = MyServiceProvider(app)
        assert p.provider_key == "my"

    def test_provider_key_explicit(self, app):
        class ExplicitProvider(Provider):
            provider_key = "custom-key"

        p = ExplicitProvider(app)
        assert p.provider_key == "custom-key"

    def test_provider_key_strips_provider_suffix(self, app):
        class DatabaseProvider(Provider):
            pass

        p = DatabaseProvider(app)
        assert p.provider_key == "database"


# ---------------------------------------------------------------------------
# register() phase
# ---------------------------------------------------------------------------


class TestRegisterPhase:
    def test_register_adds_binding_to_container(self, tmp_path):
        app = Application(base_path=tmp_path, env="testing", providers=[BindingProvider])
        assert app.make("binding_provider_service") == "bound_value"

    def test_register_multiple_providers(self, tmp_path):
        class ProviderA(Provider):
            def register(self):
                self.app.bind("svc_a", "value_a")

        class ProviderB(Provider):
            def register(self):
                self.app.bind("svc_b", "value_b")

        app = Application(base_path=tmp_path, env="testing", providers=[ProviderA, ProviderB])
        assert app.make("svc_a") == "value_a"
        assert app.make("svc_b") == "value_b"

    def test_register_is_noop_by_default(self, tmp_path):
        class NoopProvider(Provider):
            pass

        # Should not raise
        Application(base_path=tmp_path, env="testing", providers=[NoopProvider])


# ---------------------------------------------------------------------------
# boot() phase
# ---------------------------------------------------------------------------


class TestBootPhase:
    def test_boot_runs_after_register(self, tmp_path):
        call_order = []

        class TrackProvider(Provider):
            def register(self):
                call_order.append("register")
                self.app.bind("tracked", "val")

            def boot(self):
                call_order.append("boot")

        Application(base_path=tmp_path, env="testing", providers=[TrackProvider])
        assert call_order == ["register", "boot"]

    def test_boot_can_resolve_bindings_from_register(self, tmp_path):
        BootAccessProvider.resolved_in_boot = None
        Application(base_path=tmp_path, env="testing", providers=[BindingProvider, BootAccessProvider])
        assert BootAccessProvider.resolved_in_boot == "bound_value"

    def test_all_registers_run_before_any_boot(self, tmp_path):
        combined_log = []

        class PA(Provider):
            def register(self):
                combined_log.append("PA.register")

            def boot(self):
                combined_log.append("PA.boot")

        class PB(Provider):
            def register(self):
                combined_log.append("PB.register")

            def boot(self):
                combined_log.append("PB.boot")

        Application(base_path=tmp_path, env="testing", providers=[PA, PB])

        # All registers must precede all boots
        registers = [i for i, e in enumerate(combined_log) if "register" in e]
        boots = [i for i, e in enumerate(combined_log) if "boot" in e]
        assert max(registers) < min(boots)

    def test_boot_is_noop_by_default(self, tmp_path):
        class NoBootProvider(Provider):
            def register(self):
                self.app.bind("nb_svc", "val")

        Application(base_path=tmp_path, env="testing", providers=[NoBootProvider])  # Should not raise


# ---------------------------------------------------------------------------
# Duplicate key behaviour
# ---------------------------------------------------------------------------


class TestDuplicateKey:
    def test_last_write_wins(self, tmp_path):
        app = Application(base_path=tmp_path, env="testing", providers=[DuplicateKeyProvider])
        assert app.make("dup_key") == "second"


# ---------------------------------------------------------------------------
# resolve_config helper
# ---------------------------------------------------------------------------


class TestResolveConfig:
    def test_resolve_config_merges_user_over_default(self, app):
        from dataclasses import dataclass

        @dataclass
        class DefaultConfig:
            driver: str = "memory"
            ttl: int = 60

        class MergingProvider(Provider):
            result = None

            def register(self):
                merged = self.resolve_config(DefaultConfig)
                MergingProvider.result = merged

        p = MergingProvider(app, {"driver": "redis"})
        p.register()
        assert MergingProvider.result["driver"] == "redis"
        assert MergingProvider.result["ttl"] == 60

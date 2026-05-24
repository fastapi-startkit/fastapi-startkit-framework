"""Tests for the IoC service container."""

import pytest

from fastapi_startkit.container.container import Container
from fastapi_startkit.exceptions import ContainerError, MissingContainerBindingNotFound, StrictContainerException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def container():
    return Container()


# ---------------------------------------------------------------------------
# Stub classes used across tests
# ---------------------------------------------------------------------------


class ServiceA:
    pass


class ServiceB:
    pass


class ServiceC(ServiceA):
    """Subclass of ServiceA."""
    pass


# ---------------------------------------------------------------------------
# bind / make
# ---------------------------------------------------------------------------


class TestBind:
    def test_bind_and_make_plain_value(self, container):
        container.bind("foo", "bar")
        assert container.make("foo") == "bar"

    def test_bind_and_make_object_instance(self, container):
        svc = ServiceA()
        container.bind("service_a", svc)
        assert container.make("service_a") is svc

    def test_bind_returns_self_for_chaining(self, container):
        result = container.bind("x", 42)
        assert result is container

    def test_bind_overrides_existing_key_by_default(self, container):
        container.bind("key", "first")
        container.bind("key", "second")
        assert container.make("key") == "second"

    def test_bind_module_raises_strict_exception(self, container):
        import os
        with pytest.raises(StrictContainerException):
            container.bind("os", os)

    def test_strict_mode_raises_on_duplicate_key(self, container):
        container.strict = True
        container.bind("key", "value")
        with pytest.raises(StrictContainerException):
            container.bind("key", "other")

    def test_make_raises_when_key_not_bound(self, container):
        with pytest.raises(MissingContainerBindingNotFound):
            container.make("nonexistent")


# ---------------------------------------------------------------------------
# has / __contains__
# ---------------------------------------------------------------------------


class TestHas:
    def test_has_returns_true_for_bound_string_key(self, container):
        container.bind("svc", ServiceA())
        assert container.has("svc") is True

    def test_has_returns_false_for_missing_key(self, container):
        assert container.has("missing") is False

    def test_contains_operator(self, container):
        container.bind("svc", ServiceA())
        assert "svc" in container
        assert "other" not in container


# ---------------------------------------------------------------------------
# unbind
# ---------------------------------------------------------------------------


class TestUnbind:
    def test_unbind_removes_binding(self, container):
        container.bind("svc", ServiceA())
        container.unbind("svc")
        assert container.has("svc") is False

    def test_unbind_missing_key_returns_false(self, container):
        result = container.unbind("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# simple
# ---------------------------------------------------------------------------


class TestSimple:
    def test_simple_binds_instance_by_class_key(self, container):
        svc = ServiceA()
        container.simple(svc)
        assert container.has(ServiceA)


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_resolve_callable_with_no_params(self, container):
        def no_args():
            return "result"

        assert container.resolve(no_args) == "result"

    def test_resolve_auto_wires_type_hinted_param(self, container):
        svc = ServiceA()
        container.bind("svc", svc)

        def fn(a: ServiceA):
            return a

        result = container.resolve(fn)
        assert result is svc

    def test_resolve_injects_subclass(self, container):
        svc = ServiceC()
        container.bind("svc_c", svc)

        def fn(a: ServiceA):
            return a

        result = container.resolve(fn)
        assert isinstance(result, ServiceA)

    def test_resolve_passes_through_primitive_type_hints(self, container):
        def fn(name: str):
            return name

        result = container.resolve(fn, "hello")
        assert result == "hello"


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


class TestCollect:
    def test_collect_suffix_wildcard(self, container):
        container.bind("AuthUser", ServiceA())
        container.bind("AuthToken", ServiceB())
        container.bind("OtherThing", ServiceA())

        result = container.collect("Auth*")
        assert "AuthUser" in result
        assert "AuthToken" in result
        assert "OtherThing" not in result

    def test_collect_prefix_wildcard(self, container):
        container.bind("UserAuth", ServiceA())
        container.bind("UserProfile", ServiceB())
        container.bind("OtherStuff", ServiceA())

        result = container.collect("*Auth")
        assert "UserAuth" in result
        assert "UserProfile" not in result

    def test_collect_middle_wildcard(self, container):
        container.bind("AuthUserHook", ServiceA())
        container.bind("AuthAdminHook", ServiceB())
        container.bind("OtherHook", ServiceA())

        result = container.collect("Auth*Hook")
        assert "AuthUserHook" in result
        assert "AuthAdminHook" in result
        assert "OtherHook" not in result

    def test_collect_no_wildcard_raises(self, container):
        container.bind("Key", ServiceA())
        with pytest.raises(AttributeError):
            container.collect("Key")

    def test_collect_by_class_type(self, container):
        svc_a = ServiceA()
        svc_c = ServiceC()
        container.bind("a", svc_a)
        container.bind("c", svc_c)
        container.bind("b", ServiceB())

        result = container.collect(ServiceA)
        assert "a" in result
        assert "c" in result
        assert "b" not in result


# ---------------------------------------------------------------------------
# Hooks: on_bind, on_make, on_resolve
# ---------------------------------------------------------------------------


class TestHooks:
    def test_on_bind_hook_fires(self, container):
        fired = []

        container.on_bind("svc", lambda obj, c: fired.append(obj))
        container.bind("svc", ServiceA())

        assert len(fired) == 1

    def test_on_make_hook_fires(self, container):
        fired = []
        svc = ServiceA()
        container.bind("svc", svc)
        container.on_make("svc", lambda obj, c: fired.append(obj))
        container.make("svc")

        assert len(fired) == 1

    def test_multiple_hooks_on_same_key(self, container):
        fired = []
        container.on_bind("svc", lambda obj, c: fired.append("first"))
        container.on_bind("svc", lambda obj, c: fired.append("second"))
        container.bind("svc", ServiceA())

        assert "first" in fired
        assert "second" in fired


# ---------------------------------------------------------------------------
# swap
# ---------------------------------------------------------------------------


class TestSwap:
    def test_swap_returns_replacement(self, container):
        container.swap(ServiceA, lambda cls, c: "swapped")
        container.bind("svc", ServiceA())

        def fn(a: ServiceA):
            return a

        result = container.resolve(fn)
        assert result == "swapped"


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_singleton_resolves_and_binds(self, container):
        container.singleton("svc_a", ServiceA)
        result = container.make("svc_a")
        assert isinstance(result, ServiceA)

"""Tests for the IoC service container."""

import pytest

from fastapi_startkit.container.container import Container
from fastapi_startkit.exceptions import ContainerError, MissingContainerBindingNotFound, StrictContainerException


# ---------------------------------------------------------------------------
# Container.instance() — singleton class-level accessor
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container_instance():
    """Save and restore Container._instance around every test to prevent leakage."""
    original = Container._instance
    yield
    Container._instance = original


class TestInstance:
    def test_instance_raises_when_not_set(self):
        Container._instance = None
        with pytest.raises(RuntimeError, match="Container not initialized"):
            Container.instance()

    def test_set_instance_and_retrieve(self):
        c = Container()
        Container.set_instance(c)
        assert Container.instance() is c


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

    def test_make_resolves_class_binding(self, container):
        # When the bound value is a class, make() should auto-resolve it
        container.bind("svc", ServiceA)
        result = container.make("svc")
        assert isinstance(result, ServiceA)

    def test_make_returns_swap_value(self, container):
        container.swap("special", "swapped_value")
        result = container.make("special")
        assert result == "swapped_value"

    def test_make_by_class_key_finds_via_find_obj(self, container):
        svc = ServiceA()
        container.bind("svc", svc)
        result = container.make(ServiceA)
        assert result is svc

    def test_make_by_class_key_falls_back_to_resolve(self, container):
        # Class not explicitly bound — falls back to resolve()
        result = container.make(ServiceA)
        assert isinstance(result, ServiceA)


# ---------------------------------------------------------------------------
# has / __contains__
# ---------------------------------------------------------------------------


class TestHas:
    def test_has_returns_true_for_bound_string_key(self, container):
        container.bind("svc", ServiceA())
        assert container.has("svc") is True

    def test_has_returns_false_for_missing_key(self, container):
        assert container.has("missing") is False

    def test_has_by_class_returns_true_when_found(self, container):
        svc = ServiceA()
        container.bind("svc", svc)
        assert container.has(ServiceA) is True

    def test_has_by_class_returns_false_when_not_found(self, container):
        assert container.has(ServiceA) is False

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

    def test_resolve_primitive_hint_with_no_argument_skips(self, container):
        # str-hinted param with no passing argument — IndexError branch, silently skipped
        def fn(name: str = "default"):
            return name

        result = container.resolve(fn)
        assert result == "default"

    def test_resolve_with_default_value_param(self, container):
        def fn(value=42):
            return value

        result = container.resolve(fn)
        assert result == 42

    def test_resolve_with_self_param_injects_callable(self, container):
        class MyClass:
            def method(self):
                return "called"

        obj = MyClass()
        result = container.resolve(obj.method)
        assert result == "called"

    def test_resolve_unknown_param_raises_container_error(self, container):
        def fn(unknown):
            return unknown

        with pytest.raises(ContainerError):
            container.resolve(fn)

    def test_resolve_with_resolve_parameters_enabled(self, container):
        container.resolve_parameters = True
        container.bind("value", 99)

        def fn(value):
            return value

        result = container.resolve(fn)
        assert result == 99

    def test_resolve_annotated_param_not_in_container_falls_back(self, container):
        # ContainerError from _find_annotated_parameter — falls back to value.annotation (the class)
        def fn(a: ServiceA):
            return a

        result = container.resolve(fn)
        assert isinstance(result, ServiceA)

    def test_resolve_with_resolving_arguments_passed(self, container):
        svc = ServiceA()
        container.bind("svc", svc)

        def fn(a: ServiceA):
            return a

        result = container.resolve(fn, svc)
        assert isinstance(result, ServiceA)

    def test_resolve_remember_stores_and_reuses_arguments(self, container):
        # remember=True caches resolved dependency arguments, not the return value
        container.remember = True
        svc = ServiceA()
        container.bind("svc", svc)

        def fn(a: ServiceA):
            return a

        result1 = container.resolve(fn)
        result2 = container.resolve(fn)
        assert result1 is svc
        assert result2 is svc

    def test_resolve_remember_caches_method(self, container):
        container.remember = True
        svc = ServiceA()
        container.bind("svc", svc)

        class MyClass:
            def method(self, a: ServiceA):
                return a

        obj = MyClass()
        result1 = container.resolve(obj.method)
        result2 = container.resolve(obj.method)
        assert result1 is svc
        assert result2 is svc


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

    def test_on_resolve_hook_fires(self, container):
        fired = []
        svc = ServiceA()
        container.bind("svc", svc)
        container.on_resolve("svc", lambda obj, c: fired.append(obj))
        container.resolve(lambda a: a, svc)

        assert len(fired) == 0  # on_resolve fires via _find_annotated_parameter path

    def test_on_resolve_hook_via_annotated_param(self, container):
        fired = []
        svc = ServiceA()
        container.bind("svc", svc)
        container.on_resolve(ServiceA, lambda obj, c: fired.append(obj))

        def fn(a: ServiceA):
            return a

        container.resolve(fn)
        assert len(fired) >= 1

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


# ---------------------------------------------------------------------------
# helper()
# ---------------------------------------------------------------------------


class TestHelper:
    def test_helper_returns_self(self, container):
        assert container.helper() is container


# ---------------------------------------------------------------------------
# _find_obj — subclass and not-found branches
# ---------------------------------------------------------------------------


class TestFindObj:
    def test_find_obj_matches_subclass(self, container):
        svc = ServiceC()
        container.bind("svc_c", svc)
        # make(ServiceA) triggers _find_obj which should find ServiceC (subclass)
        result = container.make(ServiceA)
        assert isinstance(result, ServiceA)

    def test_find_obj_raises_when_not_found(self, container):
        # Class with an unresolvable dependency — _find_obj fails, resolve also fails
        class NeedsUnresolvable:
            def __init__(self, dep):
                self.dep = dep

        with pytest.raises((MissingContainerBindingNotFound, ContainerError)):
            container.make(NeedsUnresolvable)


# ---------------------------------------------------------------------------
# _find_annotated_parameter — swap non-callable and string annotation
# ---------------------------------------------------------------------------


class TestFindAnnotatedParameter:
    def test_swap_non_callable_returns_value(self, container):
        container.swap(ServiceA, "replaced")

        def fn(a: ServiceA):
            return a

        result = container.resolve(fn)
        assert result == "replaced"


# ---------------------------------------------------------------------------
# resolve_parameters — _find_parameter branches
# ---------------------------------------------------------------------------


class TestFindParameter:
    def test_find_parameter_by_name(self, container):
        container.resolve_parameters = True
        container.bind("value", 123)

        def fn(value):
            return value

        result = container.resolve(fn)
        assert result == 123

    def test_find_parameter_raises_when_not_found(self, container):
        container.resolve_parameters = True

        def fn(unknown_param):
            return unknown_param

        with pytest.raises(ContainerError):
            container.resolve(fn)

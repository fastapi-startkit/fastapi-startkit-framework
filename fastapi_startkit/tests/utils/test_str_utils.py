"""Tests for string utility functions (task #15)."""

from fastapi_startkit.utils.str import (
    add_query_params,
    as_filepath,
    get_controller_name,
    match,
    modularize,
    random_string,
    removeprefix,
    removesuffix,
)


class TestRandomString:
    def test_default_length_is_4(self):
        s = random_string()
        assert len(s) == 4

    def test_custom_length(self):
        assert len(random_string(10)) == 10

    def test_returns_uppercase_alphanumeric(self):
        s = random_string(100)
        assert s.isalnum()
        assert s == s.upper()

    def test_zero_length(self):
        assert random_string(0) == ""


class TestModularize:
    def test_forward_slash_replaced_by_dot(self):
        assert modularize("app/controllers/user") == "app.controllers.user"

    def test_removes_py_suffix(self):
        assert modularize("app/models/user.py") == "app.models.user"

    def test_backslash_replaced_by_dot(self):
        assert modularize("app\\controllers\\user") == "app.controllers.user"

    def test_no_extension_unchanged(self):
        assert modularize("app/views/home", suffix=".py") == "app.views.home"


class TestAsFilepath:
    def test_dots_replaced_by_slashes(self):
        assert as_filepath("app.controllers.user") == "app/controllers/user"

    def test_no_dots_unchanged(self):
        assert as_filepath("app") == "app"


class TestRemoveprefix:
    def test_removes_matching_prefix(self):
        assert removeprefix("hello world", "hello ") == "world"

    def test_no_match_returns_original(self):
        assert removeprefix("hello world", "bye") == "hello world"

    def test_empty_prefix(self):
        assert removeprefix("hello", "") == "hello"

    def test_prefix_equals_string(self):
        assert removeprefix("abc", "abc") == ""


class TestRemovesuffix:
    def test_removes_matching_suffix(self):
        assert removesuffix("hello.py", ".py") == "hello"

    def test_no_match_returns_original(self):
        assert removesuffix("hello.py", ".txt") == "hello.py"

    def test_empty_suffix(self):
        assert removesuffix("hello", "") == "hello"

    def test_suffix_equals_string(self):
        assert removesuffix("abc", "abc") == ""


class TestMatch:
    def test_exact_match(self):
        assert match("hello", "hello") is True

    def test_exact_no_match(self):
        assert match("hello", "world") is False

    def test_wildcard_suffix(self):
        assert match("hello_world", "hello*") is True
        assert match("goodbye_world", "hello*") is False

    def test_wildcard_prefix(self):
        assert match("hello_world", "*world") is True
        assert match("hello_earth", "*world") is False

    def test_wildcard_middle(self):
        assert match("hello_middle_world", "hello*world") is True
        assert match("hello_middle_earth", "hello*world") is False


class TestAddQueryParams:
    def test_adds_params_to_path(self):
        result = add_query_params("/search", {"q": "python"})
        assert "q=python" in result

    def test_merges_with_existing_params(self):
        result = add_query_params("/search?q=python", {"page": "2"})
        assert "q=python" in result
        assert "page=2" in result

    def test_preserves_fragment(self):
        result = add_query_params("/page#section", {"ref": "home"})
        assert "#section" in result
        assert "ref=home" in result

    def test_full_url_with_domain(self):
        result = add_query_params("http://example.com/path", {"key": "val"})
        assert "key=val" in result
        assert "example.com" in result

    def test_empty_params_dict_unchanged_path(self):
        result = add_query_params("/no-params", {})
        assert result == "/no-params"


class TestGetControllerName:
    def test_string_passthrough(self):
        assert get_controller_name("UserController@index") == "UserController@index"

    def test_class_with_method(self):
        class MyController:
            def show(self):
                pass

        result = get_controller_name(MyController.show)
        assert "MyController" in result
        assert "show" in result

    def test_class_without_method_uses_call(self):
        # Top-level class (no dots in __qualname__) gets @__call__ appended

        # Create a class with a simple qualname (no dots) to avoid test scope nesting
        TopLevel = type("TopLevel", (), {})
        TopLevel.__qualname__ = "TopLevel"  # force simple qualname
        result = get_controller_name(TopLevel)
        assert "TopLevel" in result
        assert "__call__" in result

    def test_instance_uses_class_qualname(self):
        class MyController:
            pass

        result = get_controller_name(MyController())
        assert "MyController" in result

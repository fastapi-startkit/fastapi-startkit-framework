"""Tests for the Uri fluent parser (task #178)."""

import pytest

from fastapi_startkit.support.uri import Uri, Uriable


class TestUriOf:
    def test_returns_uriable(self):
        result = Uri.of("https://example.com")
        assert isinstance(result, Uriable)

    def test_parse_alias(self):
        result = Uri.parse("https://example.com/path")
        assert isinstance(result, Uriable)
        assert result.path() == "/path"

    def test_get_returns_original_url(self):
        url = "https://example.com/path?q=1#frag"
        assert Uri.of(url).get() == url

    def test_str_returns_url(self):
        url = "https://example.com/path"
        assert str(Uri.of(url)) == url


class TestUriAccessors:
    def setup_method(self):
        self.uri = Uri.of("https://user:pass@example.com:8080/api/v1?page=2&sort=asc#top")

    def test_scheme(self):
        assert self.uri.scheme() == "https"

    def test_host(self):
        assert self.uri.host() == "example.com"

    def test_port(self):
        assert self.uri.port() == 8080

    def test_path(self):
        assert self.uri.path() == "/api/v1"

    def test_fragment(self):
        assert self.uri.fragment() == "top"

    def test_query_returns_dict(self):
        q = self.uri.query()
        assert q["page"] == ["2"]
        assert q["sort"] == ["asc"]

    def test_query_param_single(self):
        assert self.uri.query_param("page") == "2"
        assert self.uri.query_param("sort") == "asc"

    def test_query_param_missing_returns_default(self):
        assert self.uri.query_param("missing") is None
        assert self.uri.query_param("missing", "fallback") == "fallback"

    def test_no_port_returns_none(self):
        uri = Uri.of("https://example.com/path")
        assert uri.port() is None

    def test_no_fragment_returns_empty(self):
        uri = Uri.of("https://example.com/")
        assert uri.fragment() == ""

    def test_no_query_returns_empty_dict(self):
        uri = Uri.of("https://example.com/")
        assert uri.query() == {}


class TestWithScheme:
    def test_changes_scheme(self):
        uri = Uri.of("http://example.com/").with_scheme("https")
        assert uri.scheme() == "https"
        assert uri.get().startswith("https://")

    def test_original_unchanged(self):
        original = Uri.of("http://example.com/")
        original.with_scheme("https")
        assert original.scheme() == "http"


class TestWithHost:
    def test_replaces_host(self):
        uri = Uri.of("https://example.com/path").with_host("other.org")
        assert uri.host() == "other.org"
        assert "other.org" in uri.get()

    def test_preserves_path(self):
        uri = Uri.of("https://example.com/api/v1").with_host("api.other.com")
        assert uri.path() == "/api/v1"

    def test_preserves_query(self):
        uri = Uri.of("https://example.com/?q=1").with_host("other.com")
        assert uri.query_param("q") == "1"

    def test_preserves_port(self):
        uri = Uri.of("https://example.com:9000/").with_host("other.com")
        assert uri.port() == 9000


class TestWithPort:
    def test_sets_port(self):
        uri = Uri.of("https://example.com/").with_port(8080)
        assert uri.port() == 8080
        assert ":8080" in uri.get()

    def test_clears_port_with_none(self):
        uri = Uri.of("https://example.com:9000/").with_port(None)
        assert uri.port() is None
        assert ":9000" not in uri.get()

    def test_preserves_host(self):
        uri = Uri.of("https://example.com/").with_port(3000)
        assert uri.host() == "example.com"


class TestWithPath:
    def test_replaces_path(self):
        uri = Uri.of("https://example.com/old").with_path("/new")
        assert uri.path() == "/new"

    def test_preserves_query(self):
        uri = Uri.of("https://example.com/old?x=1").with_path("/new")
        assert uri.query_param("x") == "1"
        assert uri.path() == "/new"


class TestAppendPath:
    def test_appends_segment(self):
        uri = Uri.of("https://example.com/api").append_path("users")
        assert uri.path() == "/api/users"

    def test_handles_trailing_slash_on_base(self):
        uri = Uri.of("https://example.com/api/").append_path("users")
        assert uri.path() == "/api/users"

    def test_handles_leading_slash_on_segment(self):
        uri = Uri.of("https://example.com/api").append_path("/users")
        assert uri.path() == "/api/users"

    def test_chained_appends(self):
        uri = (
            Uri.of("https://example.com/api")
            .append_path("v1")
            .append_path("users")
        )
        assert uri.path() == "/api/v1/users"


class TestWithQuery:
    def test_replaces_all_params(self):
        uri = Uri.of("https://example.com/?a=1&b=2").with_query({"c": "3"})
        q = uri.query()
        assert "a" not in q
        assert "b" not in q
        assert q["c"] == ["3"]

    def test_accepts_int_values(self):
        uri = Uri.of("https://example.com/").with_query({"page": 5})
        assert uri.query_param("page") == "5"

    def test_accepts_list_values(self):
        uri = Uri.of("https://example.com/").with_query({"ids": [1, 2, 3]})
        assert uri.query()["ids"] == ["1", "2", "3"]


class TestAddQuery:
    def test_adds_new_param(self):
        uri = Uri.of("https://example.com/?a=1").add_query("b", "2")
        assert uri.query_param("a") == "1"
        assert uri.query_param("b") == "2"

    def test_replaces_existing_param(self):
        uri = Uri.of("https://example.com/?page=1").add_query("page", 2)
        assert uri.query_param("page") == "2"

    def test_int_value_converted(self):
        uri = Uri.of("https://example.com/").add_query("n", 42)
        assert uri.query_param("n") == "42"


class TestRemoveQuery:
    def test_removes_existing_param(self):
        uri = Uri.of("https://example.com/?a=1&b=2").remove_query("a")
        assert uri.query_param("a") is None
        assert uri.query_param("b") == "2"

    def test_noop_on_missing_key(self):
        uri = Uri.of("https://example.com/?a=1").remove_query("z")
        assert uri.query_param("a") == "1"


class TestWithFragment:
    def test_sets_fragment(self):
        uri = Uri.of("https://example.com/page").with_fragment("section-2")
        assert uri.fragment() == "section-2"
        assert "#section-2" in uri.get()

    def test_replaces_existing_fragment(self):
        uri = Uri.of("https://example.com/#old").with_fragment("new")
        assert uri.fragment() == "new"


class TestWithoutFragment:
    def test_clears_fragment(self):
        uri = Uri.of("https://example.com/#top").without_fragment()
        assert uri.fragment() == ""
        assert "#" not in uri.get()


class TestWithoutQuery:
    def test_clears_all_params(self):
        uri = Uri.of("https://example.com/?a=1&b=2").without_query()
        assert uri.query() == {}
        assert "?" not in uri.get()


class TestFluencyChaining:
    def test_full_chain(self):
        url = (
            Uri.of("http://old.example.com/api?page=1#old")
            .with_scheme("https")
            .with_host("new.example.com")
            .with_path("/v2/users")
            .add_query("page", 2)
            .add_query("limit", 50)
            .remove_query("page")
            .with_fragment("results")
            .get()
        )
        assert url == "https://new.example.com/v2/users?limit=50#results"

    def test_immutability_across_chain(self):
        original = Uri.of("https://example.com/path")
        step1 = original.with_scheme("http")
        step2 = step1.add_query("x", "1")

        assert original.scheme() == "https"
        assert original.query() == {}
        assert step1.scheme() == "http"
        assert step1.query() == {}
        assert step2.scheme() == "http"
        assert step2.query_param("x") == "1"


class TestEquality:
    def test_equal_to_same_url_string(self):
        uri = Uri.of("https://example.com/")
        assert uri == "https://example.com/"

    def test_equal_to_uriable_with_same_url(self):
        a = Uri.of("https://example.com/path")
        b = Uri.of("https://example.com/path")
        assert a == b

    def test_not_equal_to_different_url(self):
        a = Uri.of("https://example.com/a")
        b = Uri.of("https://example.com/b")
        assert a != b


class TestRepr:
    def test_repr_includes_url(self):
        uri = Uri.of("https://example.com/")
        assert "https://example.com/" in repr(uri)

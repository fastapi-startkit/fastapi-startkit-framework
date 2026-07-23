"""Unit tests for the Str / Stringable string helpers (task #1214)."""

from fastapi_startkit.support.string import Str, Stringable


class TestStrSlugify:
    def test_removes_non_alphanumeric_and_lowercases(self):
        assert Str.slugify("Hello, World!") == "helloworld"

    def test_keeps_digits(self):
        assert Str.slugify("Order #42 Ready") == "order42ready"


class TestStrTrim:
    def test_removes_word_case_insensitive(self):
        assert Str.trim("UserController", "controller") == "User"

    def test_strips_leftover_underscores(self):
        assert Str.trim("make_model_command", "command") == "make_model"

    def test_no_match_returns_stripped_original(self):
        assert Str.trim("  plain  ", "zzz") == "plain"


class TestStrCamelCase:
    def test_converts_snake_to_camel(self):
        assert Str.camel_case("make_model_command") == "makeModelCommand"

    def test_handles_spaces_and_dashes(self):
        assert Str.camel_case("some-mixed value") == "someMixedValue"

    def test_single_word_is_lowercased(self):
        assert Str.camel_case("Word") == "word"


class TestStrSnakeCase:
    def test_converts_camel_to_snake(self):
        assert Str.snake_case("makeModelCommand") == "make_model_command"

    def test_handles_acronyms(self):
        assert Str.snake_case("HTTPResponse") == "http_response"

    def test_converts_spaces_and_dashes(self):
        assert Str.snake_case("some-mixed value") == "some_mixed_value"


class TestStringableFluent:
    def test_of_returns_stringable(self):
        assert isinstance(Str.of("hello"), Stringable)

    def test_str_returns_text(self):
        assert str(Str.of("hello")) == "hello"

    def test_chaining_operations(self):
        result = Str.of("UserController").trim("Controller").snake_case()
        assert isinstance(result, Stringable)
        assert str(result) == "user"

    def test_slugify_returns_stringable(self):
        assert str(Str.of("Hi There!").slugify()) == "hithere"

    def test_camel_case_returns_stringable(self):
        assert str(Str.of("make_model").camel_case()) == "makeModel"

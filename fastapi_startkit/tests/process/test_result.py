"""Tests for ProcessResult."""

import json

import pytest

from fastapi_startkit.process.exception import ProcessFailedException, ProcessJsonDecodeError
from fastapi_startkit.process.result import ProcessResult


def _make_result(stdout="", stderr="", returncode=0, args="echo hello"):
    """Helper: build a ProcessResult from plain attributes."""
    return ProcessResult(stdout=stdout, stderr=stderr, returncode=returncode, args=args)


class TestOutput:
    def test_output_returns_stdout(self):
        r = _make_result(stdout="hello world")
        assert r.output() == "hello world"

    def test_output_returns_empty_string_when_empty(self):
        r = ProcessResult()
        assert r.output() == ""

    def test_error_output_returns_stderr(self):
        r = _make_result(stderr="something went wrong")
        assert r.error_output() == "something went wrong"

    def test_error_output_returns_empty_string_when_empty(self):
        r = ProcessResult()
        assert r.error_output() == ""

    def test_error_is_alias_for_error_output(self):
        r = _make_result(stderr="err msg")
        assert r.error() == r.error_output()
        assert r.error() == "err msg"


class TestExitCode:
    def test_exit_code_zero(self):
        r = _make_result(returncode=0)
        assert r.exit_code() == 0

    def test_exit_code_nonzero(self):
        r = _make_result(returncode=1)
        assert r.exit_code() == 1

    def test_exit_code_arbitrary(self):
        r = _make_result(returncode=127)
        assert r.exit_code() == 127


class TestSuccessfulFailed:
    def test_successful_when_returncode_zero(self):
        r = _make_result(returncode=0)
        assert r.successful() is True
        assert r.failed() is False

    def test_failed_when_returncode_nonzero(self):
        r = _make_result(returncode=1)
        assert r.failed() is True
        assert r.successful() is False

    def test_failed_with_large_code(self):
        r = _make_result(returncode=255)
        assert r.failed() is True


class TestThrow:
    def test_throw_does_not_raise_on_success(self):
        r = _make_result(returncode=0)
        result = r.throw()
        assert result is r

    def test_throw_raises_on_failure(self):
        r = _make_result(returncode=1, stderr="oops", args="bad cmd")
        with pytest.raises(ProcessFailedException) as exc_info:
            r.throw()
        assert exc_info.value.result is r

    def test_throw_exception_message_contains_command(self):
        r = _make_result(returncode=2, args="my-command")
        with pytest.raises(ProcessFailedException, match="my-command"):
            r.throw()

    def test_throw_exception_message_contains_exit_code(self):
        r = _make_result(returncode=42, args="cmd")
        with pytest.raises(ProcessFailedException, match="42"):
            r.throw()


class TestThrowIf:
    def test_throw_if_true_raises(self):
        r = _make_result(returncode=1)
        with pytest.raises(ProcessFailedException):
            r.throw_if(True)

    def test_throw_if_false_does_not_raise(self):
        r = _make_result(returncode=1)
        result = r.throw_if(False)
        assert result is r

    def test_throw_if_truthy_raises(self):
        r = _make_result(returncode=1)
        with pytest.raises(ProcessFailedException):
            r.throw_if(1)

    def test_throw_if_falsy_does_not_raise(self):
        r = _make_result(returncode=1)
        result = r.throw_if(0)
        assert result is r

    def test_throw_if_on_successful_result_does_not_raise_even_with_true(self):
        # throw_if(condition) calls throw(), which only raises when failed().
        # A successful result (returncode=0) will not raise regardless of condition.
        r = _make_result(returncode=0)
        result = r.throw_if(True)
        assert result is r


class TestCommand:
    def test_command_returns_args(self):
        r = _make_result(args="ls -la /tmp")
        assert r.command() == "ls -la /tmp"


class TestJson:
    def test_json_parses_valid_json(self):
        r = _make_result(stdout='{"key": "value", "num": 42}')
        data = r.json()
        assert data == {"key": "value", "num": 42}

    def test_json_parses_list(self):
        r = _make_result(stdout="[1, 2, 3]")
        assert r.json() == [1, 2, 3]

    def test_json_raises_on_invalid_json(self):
        r = _make_result(stdout="not valid json")
        with pytest.raises(ProcessJsonDecodeError):
            r.json()


class TestRepr:
    def test_repr_contains_exit_code(self):
        r = _make_result(returncode=0, stdout="hi")
        assert "exit_code=0" in repr(r)

    def test_repr_contains_output(self):
        r = _make_result(returncode=0, stdout="hello")
        assert "hello" in repr(r)

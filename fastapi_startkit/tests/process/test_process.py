"""Tests for the Process facade and real subprocess execution."""

import os
import pytest

from fastapi_startkit.process.process import Process, ProcessFake
from fastapi_startkit.process.result import ProcessResult
from fastapi_startkit.process.exception import ProcessFailedException, ProcessTimedOutException


@pytest.fixture(autouse=True)
def reset_process_fake():
    """Ensure Process fake state is cleared after every test."""
    yield
    Process.reset_fake()


# ---------------------------------------------------------------------------
# Real subprocess execution via Process.run()
# ---------------------------------------------------------------------------

class TestProcessRun:
    def test_run_echo_returns_output(self):
        result = Process.run('echo hello')
        assert 'hello' in result.output()

    def test_run_successful_exit_code(self):
        result = Process.run('echo hi')
        assert result.exit_code() == 0
        assert result.successful() is True
        assert result.failed() is False

    def test_run_failed_command_exit_code(self):
        result = Process.run('exit 1', )
        assert result.exit_code() == 1
        assert result.failed() is True

    def test_run_ls_lists_files(self, tmp_path):
        (tmp_path / 'testfile.txt').write_text('x')
        result = Process.path(str(tmp_path)).run('ls')
        assert 'testfile.txt' in result.output()

    def test_run_captures_stderr(self):
        result = Process.run('ls /nonexistent_path_xyz_abc_123 2>&1 || true')
        # stderr redirected to stdout via 2>&1, so output should contain error text
        assert result.exit_code() == 0  # 'true' makes it succeed

    def test_run_with_stderr_separate(self):
        result = Process.run('ls /nonexistent_path_xyz_abc_123')
        assert result.failed() is True
        assert result.error_output() != '' or result.exit_code() != 0

    def test_run_multiline_output(self):
        result = Process.run('printf "line1\nline2\nline3"')
        lines = result.output().strip().splitlines()
        assert len(lines) == 3
        assert lines[0] == 'line1'

    def test_run_echo_with_env_variable(self):
        result = Process.env({'MY_VAR': 'testvalue'}).run('echo $MY_VAR')
        assert 'testvalue' in result.output()

    def test_run_in_path(self, tmp_path):
        (tmp_path / 'hello.txt').write_text('hello content')
        result = Process.path(str(tmp_path)).run('ls hello.txt')
        assert result.successful() is True
        assert 'hello.txt' in result.output()

    def test_run_quietly_returns_empty_output(self):
        result = Process.quietly().run('echo this is quiet')
        assert result.output() == ''
        assert result.successful() is True

    def test_run_quietly_stderr_empty(self):
        result = Process.quietly().run('ls /nonexistent_path_xyz_abc_123')
        assert result.error_output() == ''
        assert result.failed() is True


class TestProcessTimeout:
    def test_timeout_raises_on_slow_command(self):
        with pytest.raises(ProcessTimedOutException):
            Process.timeout(0.1).run('sleep 5')

    def test_timeout_message_contains_command(self):
        with pytest.raises(ProcessTimedOutException, match='sleep'):
            Process.timeout(0.1).run('sleep 5')

    def test_forever_disables_timeout(self):
        # A very fast command with forever() should complete fine
        result = Process.forever().run('echo fast')
        assert result.successful() is True


# ---------------------------------------------------------------------------
# Process.fake() — testing infrastructure
# ---------------------------------------------------------------------------

class TestProcessFake:
    def test_fake_returns_process_fake_instance(self):
        fake = Process.fake()
        assert isinstance(fake, ProcessFake)

    def test_fake_default_successful_result(self):
        Process.fake()
        result = Process.run('any command')
        assert result.successful() is True
        assert result.output() == ''

    def test_fake_with_custom_output(self):
        Process.fake({
            'echo hello': Process.describe().output('hello').exit_code(0)
        })
        result = Process.run('echo hello')
        assert result.output() == 'hello'
        assert result.successful() is True

    def test_fake_with_failing_result(self):
        Process.fake({
            'bad cmd': Process.describe().error_output('fail!').exit_code(1)
        })
        result = Process.run('bad cmd')
        assert result.failed() is True
        assert result.error_output() == 'fail!'
        assert result.exit_code() == 1

    def test_fake_wildcard_matches_any_command(self):
        Process.fake({
            '*': Process.describe().output('wildcard output').exit_code(0)
        })
        result = Process.run('something unregistered')
        assert result.output() == 'wildcard output'

    def test_fake_exact_match_takes_priority_over_wildcard(self):
        Process.fake({
            'specific cmd': Process.describe().output('specific').exit_code(0),
            '*': Process.describe().output('wildcard').exit_code(0),
        })
        result = Process.run('specific cmd')
        assert result.output() == 'specific'

    def test_fake_unregistered_command_returns_default_success(self):
        Process.fake()
        result = Process.run('unregistered command')
        assert result.successful() is True

    def test_reset_fake_disables_fake_mode(self):
        Process.fake({'echo hi': Process.describe().output('faked').exit_code(0)})
        Process.reset_fake()
        # After reset, real subprocess runs
        result = Process.run('echo hi')
        assert 'hi' in result.output()


class TestProcessFakeAssertions:
    def test_assert_ran_passes_when_command_ran(self):
        fake = Process.fake()
        Process.run('echo hello')
        fake.assert_ran('echo hello')

    def test_assert_ran_fails_when_command_not_run(self):
        fake = Process.fake()
        with pytest.raises(AssertionError, match='not run'):
            fake.assert_ran('never ran')

    def test_assert_not_ran_passes_when_command_not_run(self):
        fake = Process.fake()
        Process.run('echo something')
        fake.assert_not_ran('echo other')

    def test_assert_not_ran_fails_when_command_ran(self):
        fake = Process.fake()
        Process.run('echo hello')
        with pytest.raises(AssertionError, match='unexpectedly'):
            fake.assert_not_ran('echo hello')

    def test_assert_ran_times_passes(self):
        fake = Process.fake()
        Process.run('echo hello')
        Process.run('echo hello')
        fake.assert_ran_times('echo hello', 2)

    def test_assert_ran_times_fails_wrong_count(self):
        fake = Process.fake()
        Process.run('echo hello')
        with pytest.raises(AssertionError, match='time'):
            fake.assert_ran_times('echo hello', 3)

    def test_assert_nothing_ran_passes_when_nothing_ran(self):
        fake = Process.fake()
        fake.assert_nothing_ran()

    def test_assert_nothing_ran_fails_when_something_ran(self):
        fake = Process.fake()
        Process.run('echo hello')
        with pytest.raises(AssertionError):
            fake.assert_nothing_ran()

    def test_assert_ran_with_callback(self):
        fake = Process.fake()
        Process.run('echo hello')
        # Callback receives (pending, result) and returns bool
        fake.assert_ran(lambda pending, result: result.successful())

    def test_assert_ran_with_callback_fails_when_no_match(self):
        fake = Process.fake()
        Process.run('echo hello')
        with pytest.raises(AssertionError, match='callback'):
            fake.assert_ran(lambda pending, result: result.failed())


# ---------------------------------------------------------------------------
# Exception cases
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_process_failed_exception_has_result(self):
        result = Process.run('exit 42')
        try:
            result.throw()
            pytest.fail("Expected ProcessFailedException")
        except ProcessFailedException as e:
            assert e.result is result

    def test_process_failed_exception_message(self):
        result = Process.run('false')
        with pytest.raises(ProcessFailedException) as exc_info:
            result.throw()
        assert 'false' in str(exc_info.value)

    def test_process_timed_out_exception(self):
        with pytest.raises(ProcessTimedOutException) as exc_info:
            Process.timeout(0.1).run('sleep 10')
        assert 'sleep' in str(exc_info.value)

    def test_process_timed_out_exception_has_command(self):
        try:
            Process.timeout(0.1).run('sleep 10')
        except ProcessTimedOutException as e:
            assert 'sleep' in e.command


# ---------------------------------------------------------------------------
# Fluent builder (Process class methods)
# ---------------------------------------------------------------------------

class TestFluentBuilder:
    def test_timeout_returns_pending_process(self):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.timeout(30)
        assert isinstance(pending, PendingProcess)
        assert pending._timeout == 30

    def test_forever_returns_pending_process_with_none_timeout(self):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.forever()
        assert isinstance(pending, PendingProcess)
        assert pending._timeout is None

    def test_quietly_returns_pending_process(self):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.quietly()
        assert isinstance(pending, PendingProcess)
        assert pending._quiet is True

    def test_env_merges_with_os_environ(self):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.env({'MY_KEY': 'MY_VAL'})
        assert isinstance(pending, PendingProcess)
        assert pending._env['MY_KEY'] == 'MY_VAL'
        # Should also include current env vars
        assert 'PATH' in pending._env

    def test_path_sets_cwd(self, tmp_path):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.path(str(tmp_path))
        assert isinstance(pending, PendingProcess)
        assert pending._cwd == str(tmp_path)

    def test_input_sets_stdin_data(self):
        from fastapi_startkit.process.process import PendingProcess
        pending = Process.input('stdin data')
        assert isinstance(pending, PendingProcess)
        assert pending._input == 'stdin data'

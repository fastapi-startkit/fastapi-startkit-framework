"""Tests for PendingProcess fluent builder methods."""

import os
import pytest

from fastapi_startkit.process.process import PendingProcess, ProcessFake, InvokedProcess
from fastapi_startkit.process.result import ProcessResult
from fastapi_startkit.process.exception import ProcessTimedOutException


@pytest.fixture
def pending():
    """Fresh PendingProcess with no fake."""
    return PendingProcess()


@pytest.fixture
def fake_pending():
    """PendingProcess wired to a ProcessFake."""
    fake = ProcessFake()
    return PendingProcess(fake=fake), fake


# ---------------------------------------------------------------------------
# Fluent setters
# ---------------------------------------------------------------------------

class TestFluentSetters:
    def test_timeout_sets_value(self, pending):
        result = pending.timeout(42)
        assert result is pending
        assert pending._timeout == 42

    def test_forever_sets_none(self, pending):
        result = pending.forever()
        assert result is pending
        assert pending._timeout is None

    def test_quietly_sets_flag(self, pending):
        result = pending.quietly()
        assert result is pending
        assert pending._quiet is True

    def test_tty_sets_flag(self, pending):
        result = pending.tty()
        assert result is pending
        assert pending._tty is True

    def test_tty_can_be_disabled(self, pending):
        pending.tty(True)
        result = pending.tty(False)
        assert result is pending
        assert pending._tty is False

    def test_env_merges_with_os_environ(self, pending):
        result = pending.env({'FOO': 'BAR'})
        assert result is pending
        assert pending._env['FOO'] == 'BAR'
        assert 'PATH' in pending._env  # os.environ keys still present

    def test_env_allows_override_of_existing_key(self, pending):
        original_path = os.environ.get('PATH', '')
        result = pending.env({'PATH': '/custom/path'})
        assert result is pending
        assert pending._env['PATH'] == '/custom/path'

    def test_path_sets_cwd(self, pending, tmp_path):
        result = pending.path(str(tmp_path))
        assert result is pending
        assert pending._cwd == str(tmp_path)

    def test_input_sets_stdin_data(self, pending):
        result = pending.input('some input data')
        assert result is pending
        assert pending._input == 'some input data'

    def test_chaining_multiple_setters(self, pending, tmp_path):
        result = (
            pending
            .timeout(10)
            .quietly()
            .path(str(tmp_path))
            .env({'MY': 'VAR'})
        )
        assert result is pending
        assert pending._timeout == 10
        assert pending._quiet is True
        assert pending._cwd == str(tmp_path)
        assert pending._env['MY'] == 'VAR'


# ---------------------------------------------------------------------------
# run() — real subprocess
# ---------------------------------------------------------------------------

class TestPendingProcessRun:
    def test_run_returns_process_result(self, pending):
        result = pending.run('echo hi')
        assert isinstance(result, ProcessResult)

    def test_run_captures_stdout(self, pending):
        result = pending.run('echo hello world')
        assert 'hello world' in result.output()

    def test_run_captures_stderr(self, pending):
        result = pending.run('ls /nonexistent_path_xyz_abc_123')
        assert result.failed() is True

    def test_run_with_cwd(self, tmp_path):
        (tmp_path / 'myfile.txt').write_text('content')
        p = PendingProcess()
        p.path(str(tmp_path))
        result = p.run('ls myfile.txt')
        assert result.successful() is True
        assert 'myfile.txt' in result.output()

    def test_run_with_env_variable(self, pending):
        pending.env({'TESTVAR': 'testvalue'})
        result = pending.run('echo $TESTVAR')
        assert 'testvalue' in result.output()

    def test_run_quietly_discards_output(self, pending):
        pending.quietly()
        result = pending.run('echo should not appear')
        assert result.output() == ''
        assert result.successful() is True

    def test_run_quietly_discards_stderr(self, pending):
        pending.quietly()
        result = pending.run('ls /nonexistent_path_xyz_abc_123')
        assert result.error_output() == ''
        assert result.failed() is True

    def test_run_with_input(self, pending):
        pending.input('hello from stdin\n')
        result = pending.run('cat')
        assert 'hello from stdin' in result.output()

    def test_run_timeout_raises(self, pending):
        pending.timeout(0.1)
        with pytest.raises(ProcessTimedOutException):
            pending.run('sleep 5')

    def test_run_forever_completes(self, pending):
        pending.forever()
        result = pending.run('echo quick')
        assert result.successful() is True


# ---------------------------------------------------------------------------
# run() — fake mode
# ---------------------------------------------------------------------------

class TestPendingProcessFake:
    def test_run_uses_fake_when_set(self, fake_pending):
        p, fake = fake_pending
        result = p.run('echo hello')
        assert isinstance(result, ProcessResult)
        assert result.successful() is True

    def test_run_records_command_in_fake(self, fake_pending):
        p, fake = fake_pending
        p.run('echo hello')
        fake.assert_ran('echo hello')

    def test_run_uses_registered_fake_result(self):
        from fastapi_startkit.process.process import Process
        try:
            Process.fake({
                'my command': Process.describe().output('faked output').exit_code(0)
            })
            result = Process.run('my command')
            assert result.output() == 'faked output'
        finally:
            Process.reset_fake()


# ---------------------------------------------------------------------------
# start() — async invocation
# ---------------------------------------------------------------------------

class TestPendingProcessStart:
    def test_start_returns_invoked_process(self, pending):
        invoked = pending.start('echo hello')
        assert isinstance(invoked, InvokedProcess)
        result = invoked.wait()
        assert result.successful() is True
        assert 'hello' in result.output()

    def test_start_fake_raises_not_implemented(self, fake_pending):
        p, fake = fake_pending
        with pytest.raises(NotImplementedError):
            p.start('echo hello')

    def test_start_and_wait(self, pending):
        invoked = pending.start('echo wait test')
        result = invoked.wait()
        assert isinstance(result, ProcessResult)
        assert 'wait test' in result.output()

    def test_start_running_check(self, pending):
        # echo should finish before we check, but InvokedProcess.running() should work
        invoked = pending.start('echo quick')
        result = invoked.wait()
        # After wait(), process is done
        assert invoked.running() is False

    def test_start_timeout_raises(self, pending):
        pending.timeout(0.1)
        invoked = pending.start('sleep 5')
        with pytest.raises(ProcessTimedOutException):
            invoked.wait()

    def test_start_with_callback(self, pending):
        lines_received = []

        def on_output(kind, line):
            lines_received.append((kind, line))

        invoked = pending.start('echo callback test', callback=on_output)
        result = invoked.wait()
        assert result.successful() is True
        assert any('callback test' in line for kind, line in lines_received)


# ---------------------------------------------------------------------------
# pipe()
# ---------------------------------------------------------------------------

class TestPendingProcessPipe:
    def test_pipe_runs_piped_commands(self, pending):
        result = pending.pipe(
            lambda p: (p.command('echo hello world'), p.command('grep hello'))
        )
        assert result.successful() is True
        assert 'hello' in result.output()

    def test_pipe_returns_process_result(self, pending):
        result = pending.pipe(lambda p: p.command('echo piped'))
        assert isinstance(result, ProcessResult)


# ---------------------------------------------------------------------------
# pool()
# ---------------------------------------------------------------------------

class TestPendingProcessPool:
    def test_pool_runs_multiple_commands(self, pending, tmp_path):
        from fastapi_startkit.process.process import Pool
        pool = pending.pool(
            lambda p: (p.command('echo one'), p.command('echo two'))
        )
        assert isinstance(pool, Pool)
        pool.start()
        results = pool.wait()
        assert len(results) == 2
        assert all(r.successful() for r in results)

    def test_pool_results_iterable(self, pending):
        pool = pending.pool(
            lambda p: (p.command('echo a'), p.command('echo b'), p.command('echo c'))
        )
        pool.start()
        results = pool.wait()
        count = sum(1 for _ in results)
        assert count == 3

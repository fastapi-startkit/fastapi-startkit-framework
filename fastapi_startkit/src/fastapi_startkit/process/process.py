import subprocess
import threading
import time
import os
from typing import Callable, Optional, Dict, List, Union
from .exception import ProcessFailedException, ProcessTimedOutException
from .fake import FakeProcessDescription
from .result import ProcessResult


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ProcessResult
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# FakeProcessDescription — used with Process.fake({...})
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# InvokedProcess — returned by PendingProcess.start()
# ---------------------------------------------------------------------------

class InvokedProcess:
    def __init__(self, process: subprocess.Popen, timeout=None, callback=None):
        self._process = process
        self._timeout = timeout
        self._callback = callback
        self._timed_out = False
        self._start_time = time.monotonic()
        self._stdout_buf: List[str] = []
        self._stderr_buf: List[str] = []
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._start_reader_threads()

    def _start_reader_threads(self):
        def read(pipe, kind, buf):
            for line in iter(pipe.readline, ''):
                buf.append(line)
                if self._callback:
                    self._callback(kind, line)

        if self._process.stdout:
            t = threading.Thread(
                target=read,
                args=(self._process.stdout, 'stdout', self._stdout_buf),
                daemon=True,
            )
            t.start()
            self._stdout_thread = t

        if self._process.stderr:
            t = threading.Thread(
                target=read,
                args=(self._process.stderr, 'stderr', self._stderr_buf),
                daemon=True,
            )
            t.start()
            self._stderr_thread = t

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def running(self) -> bool:
        return self._process.poll() is None

    def pid(self) -> int:
        return self._process.pid

    def signal(self, sig):
        """Send a signal to the process."""
        self._process.send_signal(sig)
        return self

    def kill(self):
        """Kill the process immediately."""
        self._process.kill()
        return self

    def ensure_not_timed_out(self):
        """Raise ProcessTimedOutException if the process has exceeded its timeout."""
        if self._timed_out:
            raise ProcessTimedOutException(self._process.args)

        if self._timeout is not None:
            elapsed = time.monotonic() - self._start_time
            if elapsed >= self._timeout:
                self._timed_out = True
                self._process.kill()
                raise ProcessTimedOutException(self._process.args)

        return self

    def wait(self) -> ProcessResult:
        """Block until the process finishes and return a ProcessResult."""
        try:
            self._process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            self._timed_out = True
            self._process.kill()
            self._process.wait()
            raise ProcessTimedOutException(self._process.args)

        for t in (self._stdout_thread, self._stderr_thread):
            if t:
                t.join()

        class _Completed:
            pass

        cp = _Completed()
        cp.args = self._process.args
        cp.stdout = ''.join(self._stdout_buf)
        cp.stderr = ''.join(self._stderr_buf)
        cp.returncode = self._process.returncode
        return ProcessResult(cp)


# ---------------------------------------------------------------------------
# Pipe — used with Process.pipe(...)
# ---------------------------------------------------------------------------

class Pipe:
    def __init__(self):
        self._commands: List[str] = []

    def command(self, cmd: str):
        self._commands.append(cmd)
        return self

    def to_command(self) -> str:
        return ' | '.join(self._commands)


# ---------------------------------------------------------------------------
# PoolResults
# ---------------------------------------------------------------------------

class PoolResults:
    def __init__(self, results: List[ProcessResult]):
        self._results = results

    def __getitem__(self, index: int) -> ProcessResult:
        return self._results[index]

    def __iter__(self):
        return iter(self._results)

    def __len__(self):
        return len(self._results)

    def successful(self) -> bool:
        return all(r.successful() for r in self._results)

    def failed(self) -> bool:
        return not self.successful()


# ---------------------------------------------------------------------------
# Pool — used with Process.pool(...)
# ---------------------------------------------------------------------------

class _PoolEntry:
    """Fluent builder for a single command inside a Pool."""
    def __init__(self, pool: 'Pool'):
        self._pool = pool
        self._command: Optional[str] = None
        self._path: Optional[str] = None

    def path(self, path: str):
        self._path = path
        return self

    def command(self, cmd: str):
        self._command = cmd
        self._pool._entries.append(self)
        return self._pool

    def _cwd(self):
        return self._path


class Pool:
    def __init__(self, env: Optional[Dict] = None, timeout=None):
        self._entries: List[_PoolEntry] = []
        self._env = env
        self._timeout = timeout
        self._invoked: List[InvokedProcess] = []

    def path(self, path: str) -> _PoolEntry:
        """Begin a pool entry, setting its working directory."""
        entry = _PoolEntry(self)
        entry._path = path
        return entry

    def command(self, cmd: str):
        """Add a command directly (no custom path)."""
        entry = _PoolEntry(self)
        entry._command = cmd
        self._entries.append(entry)
        return self

    def start(self, callback=None) -> 'Pool':
        """Start all pooled processes concurrently."""
        for i, entry in enumerate(self._entries):
            command: str = entry._command or ''
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=entry._cwd(),
                env=self._env,
            )

            def make_cb(index):
                if callback is None:
                    return None
                def _cb(kind, output):
                    callback(kind, output, index)
                return _cb

            self._invoked.append(
                InvokedProcess(proc, timeout=self._timeout, callback=make_cb(i))
            )
        return self

    def running(self) -> List[InvokedProcess]:
        """Return currently running InvokedProcesses."""
        return [p for p in self._invoked if p.running()]

    def wait(self) -> PoolResults:
        """Wait for all processes and return PoolResults."""
        return PoolResults([p.wait() for p in self._invoked])


# ---------------------------------------------------------------------------
# ProcessFake — testing infrastructure
# ---------------------------------------------------------------------------

class ProcessFake:
    def __init__(self):
        self._fakes: Dict[str, Union[FakeProcessDescription, ProcessResult]] = {}
        self._recorded: List[tuple] = []   # (command, pending, result)

    def _handle(self, command: str, pending: 'PendingProcess') -> ProcessResult:
        result = self._resolve(command)
        self._recorded.append((command, pending, result))
        return result

    def _resolve(self, command: str) -> ProcessResult:
        # Exact match first
        if command in self._fakes:
            fake = self._fakes[command]
            return fake.to_result(command) if isinstance(fake, FakeProcessDescription) else fake

        # Wildcard
        if '*' in self._fakes:
            fake = self._fakes['*']
            return fake.to_result(command) if isinstance(fake, FakeProcessDescription) else fake

        # Default: successful empty result
        class _Default:
            pass
        cp = _Default()
        cp.args = command
        cp.stdout = ''
        cp.stderr = ''
        cp.returncode = 0
        return ProcessResult(cp)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_ran(self, command_or_callback):
        """Assert a command was run. Accepts a string or an inspector callable."""
        if callable(command_or_callback):
            for cmd, pending, result in self._recorded:
                if command_or_callback(pending, result):
                    return
            raise AssertionError("No process matching the given callback was run.")

        ran = [cmd for cmd, _, __ in self._recorded]
        assert command_or_callback in ran, (
            f"Process [{command_or_callback}] was not run.\nRan: {ran}"
        )

    def assert_not_ran(self, command: str):
        ran = [cmd for cmd, _, __ in self._recorded]
        assert command not in ran, (
            f"Process [{command}] was unexpectedly run."
        )

    def assert_ran_times(self, command: str, times: int):
        count = sum(1 for cmd, _, __ in self._recorded if cmd == command)
        assert count == times, (
            f"Process [{command}] expected to run {times} time(s) but ran {count} time(s)."
        )

    def assert_nothing_ran(self):
        assert not self._recorded, (
            f"Unexpected processes were run: {[cmd for cmd, _, __ in self._recorded]}"
        )


# ---------------------------------------------------------------------------
# PendingProcess — fluent builder
# ---------------------------------------------------------------------------

class PendingProcess:
    def __init__(self, fake: Optional[ProcessFake] = None):
        self._fake = fake
        self._timeout = 60
        self._quiet = False
        self._tty = False
        self._env: Optional[Dict] = None
        self._cwd: Optional[str] = None
        self._input: Optional[str] = None

    # ------------------------------------------------------------------
    # Fluent configuration
    # ------------------------------------------------------------------

    def timeout(self, seconds: float):
        self._timeout = seconds
        return self

    def forever(self):
        """Disable timeout."""
        self._timeout = None
        return self

    def quietly(self):
        """Discard all output (stdout + stderr)."""
        self._quiet = True
        return self

    def tty(self, enabled: bool = True):
        """Allocate a TTY — passes stdin/stdout/stderr through to the terminal."""
        self._tty = enabled
        return self

    def env(self, env: Dict):
        self._env = {**os.environ, **env}
        return self

    def path(self, cwd: str):
        self._cwd = cwd
        return self

    def input(self, data: str):
        """Pipe a string into the process stdin."""
        self._input = data
        return self

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, command: str, callback: Optional[Callable] = None) -> ProcessResult:
        """Run a process synchronously and return a ProcessResult."""
        if self._fake is not None:
            return self._fake._handle(command, self)

        if self._tty:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self._cwd,
                env=self._env,
                timeout=self._timeout,
            )
            class _TtyCP:
                pass
            cp = _TtyCP()
            cp.args = command
            cp.stdout = ''
            cp.stderr = ''
            cp.returncode = result.returncode
            return ProcessResult(cp)

        if self._quiet:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self._cwd,
                env=self._env,
                input=self._input,
                timeout=self._timeout,
            )
            class _QuietCP:
                pass
            cp = _QuietCP()
            cp.args = command
            cp.stdout = ''
            cp.stderr = ''
            cp.returncode = result.returncode
            return ProcessResult(cp)

        if callback is not None:
            # Stream output through callback then return the final result
            return self.start(command, callback).wait()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._cwd,
                env=self._env,
                input=self._input,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise ProcessTimedOutException(command)
        return ProcessResult(result)

    def start(self, command: str, callback: Optional[Callable] = None) -> InvokedProcess:
        """Start a process asynchronously and return an InvokedProcess."""
        if self._fake is not None:
            raise NotImplementedError(
                "Fake async processes are not yet supported. Use run() in tests."
            )

        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self._cwd,
            env=self._env,
            stdin=subprocess.PIPE if self._input else subprocess.DEVNULL,
        )

        if self._input and proc.stdin:
            proc.stdin.write(self._input)
            proc.stdin.close()

        return InvokedProcess(proc, timeout=self._timeout, callback=callback)

    def pipe(
        self,
        callback: Callable[['Pipe'], None],
        output_callback: Optional[Callable] = None,
    ) -> ProcessResult:
        """Build a pipeline of commands and run them."""
        p = Pipe()
        callback(p)
        return self.run(p.to_command(), output_callback)

    def pool(self, callback: Callable[['Pool'], None]) -> Pool:
        """Build a pool of concurrent processes."""
        pl = Pool(env=self._env, timeout=self._timeout)
        callback(pl)
        return pl


# ---------------------------------------------------------------------------
# Process facade
# ---------------------------------------------------------------------------

class Process:
    """
    Facade mirroring Laravel's Process facade.

    Usage:
        result = Process.run('ls -la')
        result = Process.timeout(30).run('bash script.sh')
        result = Process.forever().quietly().run('bash import.sh')

        process = Process.start('bash long.sh', callback=print)
        while process.running():
            process.ensure_not_timed_out()
            time.sleep(1)
        result = process.wait()

        result = Process.pipe(lambda p: (p.command('cat file.txt'), p.command('grep foo')))

        pool = Process.pool(lambda p: (
            p.command('bash job1.sh'),
            p.command('bash job2.sh'),
        )).start(lambda kind, output, i: print(f"[{i}] {output}"))
        results = pool.wait()

    Testing:
        fake = Process.fake({'bash import.sh': Process.describe().output('ok').exit_code(0)})
        Process.run('bash import.sh')
        fake.assert_ran('bash import.sh')
        Process.reset_fake()
    """

    _fake: Optional[ProcessFake] = None

    # ------------------------------------------------------------------
    # Fake / testing
    # ------------------------------------------------------------------

    @classmethod
    def fake(
        cls,
        fakes: Optional[Dict[str, Union[FakeProcessDescription, ProcessResult]]] = None,
    ) -> ProcessFake:
        """Enable fake mode. Optionally supply per-command fakes."""
        fake = ProcessFake()
        if fakes:
            for pattern, desc in fakes.items():
                fake._fakes[pattern] = desc
        cls._fake = fake
        return fake

    @classmethod
    def reset_fake(cls):
        """Disable fake mode (call this in test teardown)."""
        cls._fake = None

    @classmethod
    def describe(cls) -> FakeProcessDescription:
        """Create a FakeProcessDescription for use with Process.fake({...})."""
        return FakeProcessDescription()

    # ------------------------------------------------------------------
    # Fluent configuration — each returns a PendingProcess
    # ------------------------------------------------------------------

    @classmethod
    def _pending(cls) -> PendingProcess:
        return PendingProcess(fake=cls._fake)

    @classmethod
    def timeout(cls, seconds: float) -> PendingProcess:
        return cls._pending().timeout(seconds)

    @classmethod
    def forever(cls) -> PendingProcess:
        return cls._pending().forever()

    @classmethod
    def quietly(cls) -> PendingProcess:
        return cls._pending().quietly()

    @classmethod
    def tty(cls, enabled: bool = True) -> PendingProcess:
        return cls._pending().tty(enabled)

    @classmethod
    def env(cls, env: Dict) -> PendingProcess:
        return cls._pending().env(env)

    @classmethod
    def path(cls, cwd: str) -> PendingProcess:
        return cls._pending().path(cwd)

    @classmethod
    def input(cls, data: str) -> PendingProcess:
        return cls._pending().input(data)

    # ------------------------------------------------------------------
    # Direct execution shortcuts
    # ------------------------------------------------------------------

    @classmethod
    def run(cls, command: str, callback: Optional[Callable] = None) -> ProcessResult:
        return cls._pending().run(command, callback)

    @classmethod
    def start(cls, command: str, callback: Optional[Callable] = None) -> InvokedProcess:
        return cls._pending().start(command, callback)

    @classmethod
    def pipe(
        cls,
        callback: Callable[['Pipe'], None],
        output_callback: Optional[Callable] = None,
    ) -> ProcessResult:
        return cls._pending().pipe(callback, output_callback)

    @classmethod
    def pool(cls, callback: Callable[['Pool'], None]) -> Pool:
        return cls._pending().pool(callback)

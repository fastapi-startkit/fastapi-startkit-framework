from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
from typing import Callable, Optional, Union

from .exception import ProcessFailedException, ProcessTimedOutException  # noqa: F401
from .fake import FakeProcessDescription
from .result import ProcessResult


# ---------------------------------------------------------------------------
# InvokedProcess — returned by PendingProcess.start()
# ---------------------------------------------------------------------------


class InvokedProcess:
    def __init__(
        self,
        process: subprocess.Popen,
        timeout: float | None = None,
        callback: Callable | None = None,
    ) -> None:
        self._process = process
        self._timeout = timeout
        self._callback = callback
        self._timed_out = False
        self._start_time = time.monotonic()
        self._stdout_buf: list[str] = []
        self._stderr_buf: list[str] = []
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._start_reader_threads()

    def _start_reader_threads(self) -> None:
        def read(pipe, kind, buf):
            for line in iter(pipe.readline, ""):
                buf.append(line)
                if self._callback:
                    self._callback(kind, line)

        if self._process.stdout:
            t = threading.Thread(
                target=read,
                args=(self._process.stdout, "stdout", self._stdout_buf),
                daemon=True,
            )
            t.start()
            self._stdout_thread = t

        if self._process.stderr:
            t = threading.Thread(
                target=read,
                args=(self._process.stderr, "stderr", self._stderr_buf),
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

    def signal(self, sig: int) -> "InvokedProcess":
        """Send a signal to the process."""
        self._process.send_signal(sig)
        return self

    def kill(self) -> "InvokedProcess":
        """Kill the process immediately."""
        self._process.kill()
        return self

    def ensure_not_timed_out(self) -> "InvokedProcess":
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

        return ProcessResult(
            stdout="".join(self._stdout_buf),
            stderr="".join(self._stderr_buf),
            returncode=self._process.returncode,
            args=self._process.args,
        )


# ---------------------------------------------------------------------------
# Pipe — used with Process.pipe(...)
# ---------------------------------------------------------------------------


class Pipe:
    def __init__(self) -> None:
        self._commands: list[str] = []

    def command(self, cmd: str) -> "Pipe":
        self._commands.append(cmd)
        return self

    def to_command(self) -> str:
        return " | ".join(self._commands)


# ---------------------------------------------------------------------------
# PoolResults
# ---------------------------------------------------------------------------


class PoolResults:
    def __init__(self, results: list[ProcessResult]) -> None:
        self._results = results

    def __getitem__(self, index: int) -> ProcessResult:
        return self._results[index]

    def __iter__(self):
        return iter(self._results)

    def __len__(self) -> int:
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

    def __init__(self, pool: "Pool") -> None:
        self._pool = pool
        self._command: str | None = None
        self._path: str | None = None

    def path(self, path: str) -> "_PoolEntry":
        self._path = path
        return self

    def command(self, cmd: str) -> "Pool":
        self._command = cmd
        self._pool._entries.append(self)
        return self._pool

    def _cwd(self) -> str | None:
        return self._path


class Pool:
    def __init__(self, env: dict | None = None, timeout: float | None = None) -> None:
        self._entries: list[_PoolEntry] = []
        self._env = env
        self._timeout = timeout
        self._invoked: list[InvokedProcess] = []

    def path(self, path: str) -> _PoolEntry:
        """Begin a pool entry, setting its working directory."""
        entry = _PoolEntry(self)
        entry._path = path
        return entry

    def command(self, cmd: str) -> "Pool":
        """Add a command directly (no custom path)."""
        entry = _PoolEntry(self)
        entry._command = cmd
        self._entries.append(entry)
        return self

    def start(self, callback: Callable | None = None) -> "Pool":
        """Start all pooled processes concurrently."""
        for i, entry in enumerate(self._entries):
            command: str = entry._command or ""
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

            self._invoked.append(InvokedProcess(proc, timeout=self._timeout, callback=make_cb(i)))
        return self

    def running(self) -> list[InvokedProcess]:
        """Return currently running InvokedProcesses."""
        return [p for p in self._invoked if p.running()]

    def wait(self) -> PoolResults:
        """Wait for all processes and return PoolResults."""
        return PoolResults([p.wait() for p in self._invoked])


# ---------------------------------------------------------------------------
# ProcessFake — testing infrastructure
# ---------------------------------------------------------------------------


class ProcessFake:
    def __init__(self) -> None:
        self._fakes: dict[str, Union[FakeProcessDescription, ProcessResult]] = {}
        self._recorded: list[tuple] = []  # (command, pending, result)

    def _handle(self, command: str, pending: "PendingProcess") -> ProcessResult:
        result = self._resolve(command)
        self._recorded.append((command, pending, result))
        return result

    def _resolve(self, command: str) -> ProcessResult:
        # Exact match first
        if command in self._fakes:
            fake = self._fakes[command]
            return fake.to_result(command) if isinstance(fake, FakeProcessDescription) else fake

        # Wildcard
        if "*" in self._fakes:
            fake = self._fakes["*"]
            return fake.to_result(command) if isinstance(fake, FakeProcessDescription) else fake

        # Default: successful empty result
        return ProcessResult(stdout="", stderr="", returncode=0, args=command)

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def assert_ran(self, command_or_callback) -> None:
        """Assert a command was run. Accepts a string or an inspector callable."""
        if callable(command_or_callback):
            for cmd, pending, result in self._recorded:
                if command_or_callback(pending, result):
                    return
            raise AssertionError("No process matching the given callback was run.")

        ran = [cmd for cmd, _, __ in self._recorded]
        assert command_or_callback in ran, f"Process [{command_or_callback}] was not run.\nRan: {ran}"

    def assert_not_ran(self, command: str) -> None:
        ran = [cmd for cmd, _, __ in self._recorded]
        assert command not in ran, f"Process [{command}] was unexpectedly run."

    def assert_ran_times(self, command: str, times: int) -> None:
        count = sum(1 for cmd, _, __ in self._recorded if cmd == command)
        assert count == times, f"Process [{command}] expected to run {times} time(s) but ran {count} time(s)."

    def assert_nothing_ran(self) -> None:
        assert not self._recorded, f"Unexpected processes were run: {[cmd for cmd, _, __ in self._recorded]}"


# ---------------------------------------------------------------------------
# PendingProcess — fluent builder
# ---------------------------------------------------------------------------


class PendingProcess:
    def __init__(self, fake: ProcessFake | None = None) -> None:
        self._fake = fake
        self._timeout: float | None = 60
        self._quiet = False
        self._tty = False
        self._env: dict | None = None
        self._cwd: str | None = None
        self._input: str | None = None

    # ------------------------------------------------------------------
    # Fluent configuration
    # ------------------------------------------------------------------

    def timeout(self, seconds: float) -> "PendingProcess":
        self._timeout = seconds
        return self

    def forever(self) -> "PendingProcess":
        """Disable timeout."""
        self._timeout = None
        return self

    def quietly(self) -> "PendingProcess":
        """Discard all output (stdout + stderr)."""
        self._quiet = True
        return self

    def tty(self, enabled: bool = True) -> "PendingProcess":
        """Allocate a TTY — passes stdin/stdout/stderr through to the terminal."""
        self._tty = enabled
        return self

    def env(self, env: dict) -> "PendingProcess":
        self._env = {**os.environ, **env}
        return self

    def path(self, cwd: str) -> "PendingProcess":
        self._cwd = cwd
        return self

    def input(self, data: str) -> "PendingProcess":
        """Pipe a string into the process stdin."""
        self._input = data
        return self

    # ------------------------------------------------------------------
    # Async execution (primary API)
    # ------------------------------------------------------------------

    async def run(self, command: str, callback: Callable | None = None) -> ProcessResult:
        """Run a process asynchronously via asyncio and return a ProcessResult."""
        if self._fake is not None:
            return self._fake._handle(command, self)

        if self._tty:
            # TTY mode: inherit stdin/stdout/stderr from parent process (no capture)
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=None,
                stdout=None,
                stderr=None,
                cwd=self._cwd,
                env=self._env,
            )
            try:
                if self._timeout is not None:
                    await asyncio.wait_for(proc.wait(), timeout=self._timeout)
                else:
                    await proc.wait()
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise ProcessTimedOutException(command)
            return ProcessResult(
                stdout="",
                stderr="",
                returncode=proc.returncode or 0,
                args=command,
            )

        stdout_pipe = asyncio.subprocess.DEVNULL if self._quiet else asyncio.subprocess.PIPE
        stderr_pipe = asyncio.subprocess.DEVNULL if self._quiet else asyncio.subprocess.PIPE
        stdin_pipe = asyncio.subprocess.PIPE if self._input else None

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            stdin=stdin_pipe,
            cwd=self._cwd,
            env=self._env,
        )

        try:
            stdin_bytes = self._input.encode() if self._input else None
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_bytes),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ProcessTimedOutException(command)

        return ProcessResult(
            stdout=(stdout_bytes.decode() if stdout_bytes else "") if not self._quiet else "",
            stderr=(stderr_bytes.decode() if stderr_bytes else "") if not self._quiet else "",
            returncode=proc.returncode or 0,
            args=command,
        )

    async def pipe(
        self,
        callback: Callable[["Pipe"], None],
        output_callback: Callable | None = None,
    ) -> ProcessResult:
        """Build a pipeline of commands and run them asynchronously."""
        p = Pipe()
        callback(p)
        return await self.run(p.to_command(), output_callback)

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    def start(self, command: str, callback: Callable | None = None) -> InvokedProcess:
        """Start a process in the background and return an InvokedProcess."""
        if self._fake is not None:
            raise NotImplementedError("Fake background processes are not yet supported. Use run() in tests.")

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

    def pool(self, callback: Callable[["Pool"], None]) -> Pool:
        """Build a pool of concurrent processes."""
        pl = Pool(env=self._env, timeout=self._timeout)
        callback(pl)
        return pl


# ---------------------------------------------------------------------------
# Process facade
# ---------------------------------------------------------------------------


class Process:
    """
    Facade for running shell commands.

    Primary API — async (for use inside FastAPI request handlers):
        result = await Process.run('ls -la')
        result = await Process.timeout(30).run('bash script.sh')
        result = await Process.forever().quietly().run('bash import.sh')

    Background execution:
        process = Process.start('bash long.sh', callback=print)
        while process.running():
            process.ensure_not_timed_out()
            time.sleep(1)
        result = process.wait()

    Pipelines:
        result = await Process.pipe(lambda p: (p.command('cat f.txt'), p.command('grep foo')))

    Pools (concurrent):
        pool = Process.pool(lambda p: (
            p.command('bash job1.sh'),
            p.command('bash job2.sh'),
        )).start(lambda kind, output, i: print(f"[{i}] {output}"))
        results = pool.wait()

    Testing:
        fake = Process.fake({'bash import.sh': Process.describe().output('ok').exit_code(0)})
        await Process.run('bash import.sh')
        fake.assert_ran('bash import.sh')
        Process.reset_fake()
    """

    _fake: ProcessFake | None = None

    # ------------------------------------------------------------------
    # Fake / testing
    # ------------------------------------------------------------------

    @classmethod
    def fake(
        cls,
        fakes: dict[str, Union[FakeProcessDescription, ProcessResult]] | None = None,
    ) -> ProcessFake:
        """Enable fake mode. Optionally supply per-command fakes."""
        fake = ProcessFake()
        if fakes:
            for pattern, desc in fakes.items():
                fake._fakes[pattern] = desc
        cls._fake = fake
        return fake

    @classmethod
    def reset_fake(cls) -> None:
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
    def env(cls, env: dict) -> PendingProcess:
        return cls._pending().env(env)

    @classmethod
    def path(cls, cwd: str) -> PendingProcess:
        return cls._pending().path(cwd)

    @classmethod
    def input(cls, data: str) -> PendingProcess:
        return cls._pending().input(data)

    # ------------------------------------------------------------------
    # Async execution shortcuts (primary API)
    # ------------------------------------------------------------------

    @classmethod
    async def run(cls, command: str, callback: Callable | None = None) -> ProcessResult:
        """Run a command asynchronously (primary API)."""
        return await cls._pending().run(command, callback)

    @classmethod
    async def pipe(
        cls,
        callback: Callable[["Pipe"], None],
        output_callback: Callable | None = None,
    ) -> ProcessResult:
        """Build a pipeline of commands and run them asynchronously."""
        return await cls._pending().pipe(callback, output_callback)

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    @classmethod
    def start(cls, command: str, callback: Callable | None = None) -> InvokedProcess:
        """Start a command in the background, returning an InvokedProcess."""
        return cls._pending().start(command, callback)

    @classmethod
    def pool(cls, callback: Callable[["Pool"], None]) -> Pool:
        """Build a pool of concurrent processes."""
        return cls._pending().pool(callback)

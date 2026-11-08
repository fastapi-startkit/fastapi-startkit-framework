import asyncio
import hashlib
import json
import os
import pickle
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .lock import Lock
from .store import MISSING, Missing, expired, expires_at

SHARD = re.compile(r"^[0-9a-f]{2}$")
Holder = tuple[str, float | None] | None
Decision = tuple[bool, Holder | Missing]


class FileStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode()).hexdigest()
        return self.directory / digest[:2] / digest[2:4] / digest

    async def get(self, key: str) -> Any:
        return await asyncio.to_thread(self.read, self.path(key))

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        payload = pickle.dumps((expires_at(seconds), value))
        await asyncio.to_thread(self.write, self.path(key), payload)
        return True

    async def forget(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, self.path(key))

    async def flush(self) -> bool:
        await asyncio.to_thread(self.clear)
        return True

    def read(self, path: Path) -> Any:
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return MISSING
        try:
            expiration, value = pickle.loads(payload)
        except Exception:
            self.delete(path)
            return MISSING

        if expired(expiration):
            self.delete(path)
            return MISSING
        return value

    def write(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(payload)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def delete(self, path: Path) -> bool:
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def clear(self) -> None:
        if not self.directory.is_dir():
            return
        for shard in self.directory.iterdir():
            if shard.is_dir() and SHARD.match(shard.name):
                shutil.rmtree(shard, ignore_errors=True)

    def lock(self, name: str, seconds: float = 0, owner: str | None = None) -> "FileLock":
        return FileLock(self, name, seconds, owner)


class FileLock(Lock):
    def __init__(self, store: FileStore, name: str, seconds: float = 0, owner: str | None = None):
        super().__init__(name, seconds, owner)
        self.path = store.directory / "locks" / hashlib.sha1(name.encode()).hexdigest()

    async def acquire(self) -> bool:
        def decide(holder: Holder) -> Decision:
            if holder is not None:
                return False, MISSING
            return True, (self.owner, expires_at(self.ttl))

        return await asyncio.to_thread(self.exclusive, decide)

    async def release(self) -> bool:
        def decide(holder: Holder) -> Decision:
            if holder is None or holder[0] != self.owner:
                return False, MISSING
            return True, None

        return await asyncio.to_thread(self.exclusive, decide)

    async def force_release(self) -> None:
        await asyncio.to_thread(self.exclusive, lambda holder: (True, None))

    def exclusive(self, decide: Callable[[Holder], Decision]) -> bool:
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+b") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            file.seek(0)
            result, holder = decide(self.read(file.read()))
            if holder is not MISSING:
                file.truncate(0)
                if holder is not None:
                    file.write(json.dumps(holder).encode())
                file.flush()
            return result

    def read(self, payload: bytes) -> Holder:
        try:
            owner, expiration = json.loads(payload)
        except (ValueError, TypeError):
            return None
        if not isinstance(owner, str) or not isinstance(expiration, int | float | None) or expired(expiration):
            return None
        return owner, expiration

import asyncio
import hashlib
import os
import pickle
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .store import MISSING, expired, expires_at

SHARD = re.compile(r"^[0-9a-f]{2}$")


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

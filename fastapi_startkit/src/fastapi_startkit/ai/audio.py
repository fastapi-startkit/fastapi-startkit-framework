"""Audio generation API — text-to-speech via OpenAI TTS."""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional

# Optional runtime dependencies — imported at module level so tests can patch them.
try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment,misc]

try:
    from fastapi_startkit.storage.storage import Storage
except Exception:  # pragma: no cover
    Storage = None  # type: ignore[assignment,misc]


class AudioResponse:
    """Returned by :meth:`Audio.generate`.

    Holds raw MP3 (or other format) bytes and provides async helpers to
    persist the audio to any configured storage disk::

        audio = await Audio.of("Hello world").generate()

        path = await audio.store()                     # auto-named, private disk
        path = await audio.storeAs("greeting.mp3")     # named, private disk
        path = await audio.storePublicly()             # auto-named, public disk
        path = await audio.storePubliclyAs("greeting.mp3")
    """

    def __init__(self, data: bytes, fmt: str = "mp3"):
        self._data = data
        self._fmt = fmt

    @property
    def data(self) -> bytes:
        """Raw audio bytes."""
        return self._data

    def _auto_filename(self) -> str:
        return f"{uuid.uuid4()}.{self._fmt}"

    # ── Storage helpers ────────────────────────────────────────────────────────

    async def store(self) -> str:
        """Save to the default private disk with an auto-generated filename."""
        return await self._save(self._auto_filename(), disk="local")

    async def storeAs(self, name: str) -> str:
        """Save to the default private disk with a custom filename."""
        return await self._save(name, disk="local")

    async def storePublicly(self) -> str:
        """Save to the public disk with an auto-generated filename."""
        return await self._save(self._auto_filename(), disk="public")

    async def storePubliclyAs(self, name: str) -> str:
        """Save to the public disk with a custom filename."""
        return await self._save(name, disk="public")

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _save(self, name: str, disk: str = "local") -> str:
        return await asyncio.to_thread(self._save_sync, name, disk)

    def _save_sync(self, name: str, disk: str) -> str:
        """Try the Storage facade first; fall back to a temp file."""
        if Storage is not None:
            try:
                Storage.disk(disk).put(name, self._data)
                return name
            except Exception:
                pass
        import os
        import tempfile

        path = os.path.join(tempfile.gettempdir(), name)
        with open(path, "wb") as f:
            f.write(self._data)
        return path


class Audio:
    """Fluent builder for text-to-speech generation.

    Usage::

        audio = await Audio.of("Hello world").generate()
        audio = await Audio.of("Hello world").female().generate()
        audio = await Audio.of("Hello world").male().generate()
        audio = await Audio.of("Hello world").voice("nova").generate()

    Available OpenAI TTS voices: alloy, echo, fable, onyx, nova, shimmer.
    """

    # OpenAI TTS voice presets
    _DEFAULT_VOICE = "alloy"
    _DEFAULT_FEMALE_VOICE = "nova"
    _DEFAULT_MALE_VOICE = "onyx"

    def __init__(self, text: str):
        self._text = text
        self._voice: str = self._DEFAULT_VOICE
        self._model: str = "tts-1"
        self._speed: float = 1.0
        self._response_format: str = "mp3"

    @classmethod
    def of(cls, text: str) -> "Audio":
        """Create an :class:`Audio` builder with the given input text."""
        return cls(text)

    # ── Modifier methods (chainable) ───────────────────────────────────────────

    def female(self) -> "Audio":
        """Use a female voice (``nova``)."""
        self._voice = self._DEFAULT_FEMALE_VOICE
        return self

    def male(self) -> "Audio":
        """Use a male voice (``onyx``)."""
        self._voice = self._DEFAULT_MALE_VOICE
        return self

    def voice(self, name: str) -> "Audio":
        """Set an explicit OpenAI TTS voice name.

        Available voices: ``alloy``, ``echo``, ``fable``, ``onyx``, ``nova``,
        ``shimmer``.
        """
        self._voice = name
        return self

    def model(self, name: str) -> "Audio":
        """Override the TTS model (default: ``tts-1``).

        Use ``tts-1-hd`` for higher quality at the cost of latency.
        """
        self._model = name
        return self

    def speed(self, value: float) -> "Audio":
        """Set speech speed (0.25 – 4.0, default: 1.0)."""
        self._speed = value
        return self

    def format(self, fmt: str) -> "Audio":
        """Set output format: ``mp3``, ``opus``, ``aac``, or ``flac``."""
        self._response_format = fmt
        return self

    # ── Generation ─────────────────────────────────────────────────────────────

    async def generate(self) -> AudioResponse:
        """Call the TTS API and return an :class:`AudioResponse`."""
        return await asyncio.to_thread(self._generate_sync)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _generate_sync(self) -> AudioResponse:
        client = OpenAI(api_key=self._resolve_api_key())
        response = client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=self._text,
            speed=self._speed,
            response_format=self._response_format,
        )
        data = response.read()
        return AudioResponse(data=data, fmt=self._response_format)

    def _resolve_api_key(self) -> Optional[str]:
        try:
            from fastapi_startkit.facades.Config import Config  # noqa: PLC0415

            ai_config = Config.get("ai")
            return ai_config.providers["openai"].key or None
        except Exception:
            return None

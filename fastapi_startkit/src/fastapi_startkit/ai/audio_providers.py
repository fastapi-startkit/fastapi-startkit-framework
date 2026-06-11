"""Audio synthesis provider abstractions.

Providers implement the :class:`AudioSynthesisProvider` ABC so that the
:class:`~fastapi_startkit.ai.Audio` builder is not hard-wired to a single
vendor.  Select the active provider via ``AI_AUDIO_PROVIDER`` in your
``.env`` (or ``AIConfig.audio_provider``).

Supported providers
-------------------
* ``openai``     — OpenAI TTS (tts-1 / tts-1-hd) (default)
* ``elevenlabs`` — ElevenLabs (stub, raises :exc:`NotImplementedError`)
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AudioSynthesisProvider(ABC):
    """Abstract base for text-to-speech backends."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
        fmt: str,
    ) -> bytes:
        """Convert *text* to speech and return raw audio bytes."""


class OpenAIAudioProvider(AudioSynthesisProvider):
    """OpenAI TTS provider using :class:`openai.AsyncOpenAI`.

    Supported voices: ``alloy``, ``echo``, ``fable``, ``onyx``, ``nova``,
    ``shimmer``.  Supported formats: ``mp3``, ``opus``, ``aac``, ``flac``.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url

    async def synthesize(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
        fmt: str,
    ) -> bytes:
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format=fmt,
        )
        return response.read()


class ElevenLabsAudioProvider(AudioSynthesisProvider):
    """ElevenLabs provider stub — raises :exc:`NotImplementedError` until implemented."""

    async def synthesize(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
        fmt: str,
    ) -> bytes:
        raise NotImplementedError("ElevenLabsAudioProvider is not yet implemented")

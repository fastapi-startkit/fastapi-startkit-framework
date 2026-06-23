"""Audio synthesis provider abstractions.

Providers implement the :class:`AudioFactory` ABC so that the
:class:`~fastapi_startkit.ai.Audio` builder is not hard-wired to a single
vendor.  Select the active provider via ``AI_AUDIO_PROVIDER`` in your
``.env`` (or ``AIConfig.default_audio``).

Supported providers
-------------------
* ``openai``     — OpenAI TTS (tts-1 / tts-1-hd) (default)
* ``google``     — Google Gemini TTS via the ``google-genai`` SDK
* ``elevenlabs`` — ElevenLabs TTS via the ``elevenlabs`` SDK
"""

from __future__ import annotations

import asyncio
import struct
from abc import ABC, abstractmethod


class AudioFactory(ABC):
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


class OpenAIAudioFactory(AudioFactory):
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


class GoogleAudioFactory(AudioFactory):
    """Google Gemini TTS provider via the ``google-genai`` SDK.

    Requires: ``pip install google-genai``

    Configure via ``.env``::

        AI_AUDIO_PROVIDER=google
        GEMINI_API_KEY=your-key        # or GOOGLE_API_KEY

    Default model: ``gemini-2.5-flash-preview-tts``.

    Google voice names (pass via :meth:`~fastapi_startkit.ai.Audio.voice`):
    ``Kore``, ``Aoede``, ``Puck``, ``Charon``, ``Fenrir``, ``Leda``,
    ``Orus``, ``Zephyr``.

    OpenAI-compatible voice aliases are also accepted and mapped
    automatically:

    +----------+-------------+
    | Alias    | Google voice|
    +==========+=============+
    | nova     | Aoede       |
    | alloy    | Kore        |
    | echo     | Charon      |
    | fable    | Puck        |
    | onyx     | Fenrir      |
    | shimmer  | Leda        |
    +----------+-------------+

    The provider returns **WAV** bytes regardless of the requested format,
    because Gemini TTS yields raw PCM16 which is wrapped in a WAV container.
    """

    # Map OpenAI-style voice aliases → Google Gemini voice names
    _VOICE_MAP: dict[str, str] = {
        "nova": "Aoede",
        "alloy": "Kore",
        "echo": "Charon",
        "fable": "Puck",
        "onyx": "Fenrir",
        "shimmer": "Leda",
    }

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
        fmt: str,
    ) -> bytes:
        """Synthesise *text* via Gemini TTS and return WAV bytes.

        .. note::
            The ``speed`` parameter is accepted for API compatibility but is
            not currently supported by the Gemini TTS API.
        """
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        client = genai.Client(api_key=self._api_key)
        google_voice = self._VOICE_MAP.get(voice, voice)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=google_voice,
                        )
                    )
                ),
            ),
        )

        # Gemini TTS returns raw PCM16 samples — wrap in WAV container
        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        return _pcm_to_wav(pcm_data)


class ElevenLabsAudioFactory(AudioFactory):
    """ElevenLabs TTS provider via the ``elevenlabs`` SDK.

    Requires: ``pip install elevenlabs``

    Configure via ``.env``::

        AI_AUDIO_PROVIDER=elevenlabs
        ELEVENLABS_API_KEY=your-key

    Voice names are mapped to ElevenLabs voice IDs.  You can pass any
    ElevenLabs voice ID directly via :meth:`~fastapi_startkit.ai.Audio.voice`,
    or use one of the built-in aliases:

    +----------+----------------+---------+
    | Alias    | EL Name        | Gender  |
    +==========+================+=========+
    | nova     | Rachel         | female  |
    | alloy    | Bella          | female  |
    | shimmer  | Elli           | female  |
    | onyx     | Adam           | male    |
    | echo     | Antoni         | male    |
    | fable    | Arnold         | male    |
    +----------+----------------+---------+

    Default model: ``eleven_multilingual_v2``.
    Override with :meth:`~fastapi_startkit.ai.Audio.model`.

    .. note::
        The ``speed`` parameter is accepted for API compatibility but is
        not currently supported by ElevenLabs.
    """

    # Map OpenAI-style aliases → ElevenLabs voice IDs
    _VOICE_MAP: dict[str, str] = {
        "nova": "21m00Tcm4TlvDq8ikWAM",  # Rachel — female
        "alloy": "EXAVITQu4vr4xnSDxMaL",  # Bella  — female
        "shimmer": "MF3mGyEYCl7XYWbV9V6O",  # Elli   — female
        "onyx": "pNInz6obpgDQGcFmaJgB",  # Adam   — male
        "echo": "ErXwobaYiN019PkySvjV",  # Antoni — male
        "fable": "VR6AewLTigWG4xSOukaG",  # Arnold — male
    }

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice: str,
        model: str,
        speed: float,
        fmt: str,
    ) -> bytes:
        from elevenlabs.client import ElevenLabs  # noqa: PLC0415

        voice_id = self._VOICE_MAP.get(voice, voice)
        client = ElevenLabs(api_key=self._api_key)

        audio_chunks = await asyncio.to_thread(
            client.text_to_speech.convert,
            voice_id=voice_id,
            text=text,
            model_id=model,
            output_format="mp3_44100_128",
        )
        return b"".join(audio_chunks)


# ─── PCM → WAV helper ─────────────────────────────────────────────────────────


def _pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    bit_depth: int = 16,
) -> bytes:
    """Wrap raw PCM16 samples in a minimal RIFF/WAV container.

    Gemini TTS returns signed 16-bit little-endian PCM at 24 kHz mono.
    Most audio players and APIs accept WAV, so we wrap it here.
    """
    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
        b"data",
        data_size,
    )
    return header + pcm_data

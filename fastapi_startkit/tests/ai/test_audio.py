"""Tests for the Audio generation API (Audio, AudioResponse)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi_startkit.ai.audio import Audio, AudioResponse


# ─── Shared fixtures ──────────────────────────────────────────────────────────


def _fake_audio_bytes() -> bytes:
    return b"ID3\x03\x00"  # minimal MP3 magic


def _mock_provider(result: bytes | None = None) -> MagicMock:
    """Return a mock AudioFactory."""
    p = MagicMock()
    p.synthesize = AsyncMock(return_value=result if result is not None else _fake_audio_bytes())
    return p


# ─── Audio builder — chainable API ────────────────────────────────────────────


class TestAudioBuilder:
    def test_of_returns_audio_instance(self):
        audio = Audio.of("Hello world")
        assert isinstance(audio, Audio)
        assert audio._text == "Hello world"

    def test_default_voice_is_alloy(self):
        audio = Audio.of("Hello")
        assert audio._voice == "alloy"

    def test_female_sets_nova_voice(self):
        audio = Audio.of("Hello").female()
        assert audio._voice == "nova"

    def test_male_sets_onyx_voice(self):
        audio = Audio.of("Hello").male()
        assert audio._voice == "onyx"

    def test_voice_sets_explicit_voice(self):
        audio = Audio.of("Hello").voice("shimmer")
        assert audio._voice == "shimmer"

    def test_voice_overrides_previous_setting(self):
        audio = Audio.of("Hello").female().voice("echo")
        assert audio._voice == "echo"

    def test_model_override(self):
        audio = Audio.of("Hello").model("tts-1-hd")
        assert audio._model == "tts-1-hd"

    def test_speed_override(self):
        audio = Audio.of("Hello").speed(1.5)
        assert audio._speed == 1.5

    def test_format_override(self):
        audio = Audio.of("Hello").format("opus")
        assert audio._response_format == "opus"

    def test_chainable_methods_return_self(self):
        audio = Audio.of("Hello")
        assert audio.female() is audio
        assert audio.male() is audio
        assert audio.voice("alloy") is audio
        assert audio.model("tts-1") is audio
        assert audio.speed(1.0) is audio
        assert audio.format("mp3") is audio


# ─── Audio.generate() ─────────────────────────────────────────────────────────


class TestAudioGeneration:
    @pytest.mark.asyncio
    async def test_generate_calls_provider_and_returns_response(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            result = await Audio.of("Hello world").generate()

        assert isinstance(result, AudioResponse)
        assert result.data == _fake_audio_bytes()
        provider.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_passes_text_to_provider(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hello world").generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_female_passes_nova_voice(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").female().generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["voice"] == "nova"

    @pytest.mark.asyncio
    async def test_generate_male_passes_onyx_voice(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").male().generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["voice"] == "onyx"

    @pytest.mark.asyncio
    async def test_generate_explicit_voice(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").voice("shimmer").generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["voice"] == "shimmer"

    @pytest.mark.asyncio
    async def test_generate_passes_speed(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").speed(1.25).generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["speed"] == 1.25

    @pytest.mark.asyncio
    async def test_generate_passes_format(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").format("opus").generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["fmt"] == "opus"

    @pytest.mark.asyncio
    async def test_generate_hd_model(self):
        provider = _mock_provider()

        with patch.object(Audio, "_resolve_provider", return_value=provider):
            await Audio.of("Hi").model("tts-1-hd").generate()

        call_kwargs = provider.synthesize.call_args[1]
        assert call_kwargs["model"] == "tts-1-hd"


# ─── AudioResponse storage methods ────────────────────────────────────────────


class TestAudioResult:
    @pytest.mark.asyncio
    async def test_store_writes_to_temp_when_no_storage(self):
        resp = AudioResponse(data=_fake_audio_bytes())

        path = await resp.store()

        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == _fake_audio_bytes()
        os.remove(path)

    @pytest.mark.asyncio
    async def test_store_as_uses_given_name(self):
        resp = AudioResponse(data=_fake_audio_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/greeting.mp3"
            await resp.storeAs("greeting.mp3")

        mock_save.assert_called_once_with("greeting.mp3", "local")

    @pytest.mark.asyncio
    async def test_store_publicly_as_uses_public_disk(self):
        resp = AudioResponse(data=_fake_audio_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/greeting.mp3"
            await resp.storePubliclyAs("greeting.mp3")

        mock_save.assert_called_once_with("greeting.mp3", "public")

    @pytest.mark.asyncio
    async def test_store_publicly_uses_public_disk(self):
        resp = AudioResponse(data=_fake_audio_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.mp3"
            await resp.storePublicly()

        _, disk = mock_save.call_args[0]
        assert disk == "public"

    @pytest.mark.asyncio
    async def test_store_auto_filename_has_mp3_ext(self):
        resp = AudioResponse(data=_fake_audio_bytes(), fmt="mp3")

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.mp3"
            await resp.store()

        name, _ = mock_save.call_args[0]
        assert name.endswith(".mp3")

    @pytest.mark.asyncio
    async def test_store_uses_storage_facade_when_available(self):
        resp = AudioResponse(data=_fake_audio_bytes())
        mock_disk = MagicMock()

        with patch("fastapi_startkit.ai.audio.Storage") as mock_storage_cls:
            mock_storage_cls.disk.return_value = mock_disk
            await resp.storeAs("hello.mp3")

        mock_storage_cls.disk.assert_called_once_with("local")
        mock_disk.put.assert_called_once_with("hello.mp3", _fake_audio_bytes())


# ─── GoogleAudioFactory ──────────────────────────────────────────────────────


class TestGoogleAudioFactory:
    @pytest.mark.asyncio
    async def test_synthesize_returns_wav_bytes(self):
        from fastapi_startkit.ai.audio_factory import GoogleAudioFactory

        fake_pcm = b"\x00\x01" * 100  # 200 bytes of fake PCM16

        mock_part = MagicMock()
        mock_part.inline_data.data = fake_pcm
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]

        mock_google = MagicMock()
        mock_google_types = MagicMock()

        provider = GoogleAudioFactory(api_key="test-key")

        with patch.dict(
            "sys.modules", {"google": mock_google, "google.genai": mock_google, "google.genai.types": mock_google_types}
        ):
            with patch(
                "fastapi_startkit.ai.audio_factory.asyncio.to_thread", new=AsyncMock(return_value=mock_response)
            ):
                result = await provider.synthesize("Hello world", "nova", "gemini-2.5-flash-preview-tts", 1.0, "mp3")

        # Result must be a valid WAV: starts with RIFF header
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WAVE"

    def test_voice_map_covers_openai_aliases(self):
        from fastapi_startkit.ai.audio_factory import GoogleAudioFactory

        provider = GoogleAudioFactory()
        assert provider._VOICE_MAP["nova"] == "Aoede"
        assert provider._VOICE_MAP["onyx"] == "Fenrir"
        assert provider._VOICE_MAP["alloy"] == "Kore"

    def test_unknown_voice_passed_through(self):
        from fastapi_startkit.ai.audio_factory import GoogleAudioFactory

        provider = GoogleAudioFactory()
        assert provider._VOICE_MAP.get("Zephyr", "Zephyr") == "Zephyr"

    @pytest.mark.asyncio
    async def test_audio_builder_resolves_google_provider(self):
        mock_ai_config = MagicMock()
        mock_ai_config.audio_provider = "google"
        mock_ai_config.providers = {
            "google": MagicMock(key="gkey"),
            "openai": MagicMock(key=""),
            "elevenlabs": MagicMock(key=""),
        }

        with patch("fastapi_startkit.ai.audio.Config") as mock_config:
            mock_config.get.return_value = mock_ai_config
            from fastapi_startkit.ai.audio import Audio
            from fastapi_startkit.ai.audio_factory import GoogleAudioFactory

            provider = Audio.of("test")._resolve_provider()

        assert isinstance(provider, GoogleAudioFactory)


# ─── _pcm_to_wav helper ───────────────────────────────────────────────────────


class TestPcmToWav:
    def test_wav_header_structure(self):
        from fastapi_startkit.ai.audio_factory import _pcm_to_wav

        pcm = b"\x00\x00" * 24000  # 1 second of silence at 24kHz mono 16-bit
        wav = _pcm_to_wav(pcm)

        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert wav[12:16] == b"fmt "
        assert wav[36:40] == b"data"

    def test_wav_size_matches_pcm(self):
        from fastapi_startkit.ai.audio_factory import _pcm_to_wav

        pcm = b"\x01\x02" * 100
        wav = _pcm_to_wav(pcm)
        assert len(wav) == 44 + len(pcm)


# ─── ElevenLabsAudioFactory ──────────────────────────────────────────────────


class TestElevenLabsAudioFactory:
    @pytest.mark.asyncio
    async def test_synthesize_joins_audio_chunks(self):
        from fastapi_startkit.ai.audio_factory import ElevenLabsAudioFactory

        fake_chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter(fake_chunks)

        mock_elevenlabs_module = MagicMock()
        provider = ElevenLabsAudioFactory(api_key="test-key")

        with patch.dict(
            "sys.modules", {"elevenlabs": mock_elevenlabs_module, "elevenlabs.client": mock_elevenlabs_module}
        ):
            with patch(
                "fastapi_startkit.ai.audio_factory.asyncio.to_thread", new=AsyncMock(return_value=iter(fake_chunks))
            ):
                result = await provider.synthesize("Hello", "nova", "eleven_multilingual_v2", 1.0, "mp3")

        assert result == b"chunk1chunk2chunk3"

    def test_voice_map_covers_openai_aliases(self):
        from fastapi_startkit.ai.audio_factory import ElevenLabsAudioFactory

        provider = ElevenLabsAudioFactory()
        assert "nova" in provider._VOICE_MAP
        assert "onyx" in provider._VOICE_MAP
        assert "echo" in provider._VOICE_MAP

    def test_direct_voice_id_passed_through(self):
        from fastapi_startkit.ai.audio_factory import ElevenLabsAudioFactory

        provider = ElevenLabsAudioFactory()
        # Unknown voice name → passed as-is (user's own voice ID)
        direct_id = "some-custom-voice-id"
        resolved = provider._VOICE_MAP.get(direct_id, direct_id)
        assert resolved == direct_id

    @pytest.mark.asyncio
    async def test_audio_builder_resolves_elevenlabs_provider(self):
        mock_ai_config = MagicMock()
        mock_ai_config.audio_provider = "elevenlabs"
        mock_ai_config.providers = {
            "google": MagicMock(key=""),
            "openai": MagicMock(key=""),
            "elevenlabs": MagicMock(key="elkey"),
        }

        with patch("fastapi_startkit.ai.audio.Config") as mock_config:
            mock_config.get.return_value = mock_ai_config
            from fastapi_startkit.ai.audio import Audio
            from fastapi_startkit.ai.audio_factory import ElevenLabsAudioFactory

            provider = Audio.of("test")._resolve_provider()

        assert isinstance(provider, ElevenLabsAudioFactory)
        assert provider._api_key == "elkey"

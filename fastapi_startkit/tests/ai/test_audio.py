"""Tests for the Audio generation API (Audio, AudioResponse)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.ai.audio import Audio, AudioResponse


# ─── Audio builder — chainable API ───────────────────────────────────────────


def test_audio_of_returns_audio_instance():
    audio = Audio.of("Hello world")
    assert isinstance(audio, Audio)
    assert audio._text == "Hello world"


def test_audio_default_voice_is_alloy():
    audio = Audio.of("Hello")
    assert audio._voice == "alloy"


def test_audio_female_sets_nova_voice():
    audio = Audio.of("Hello").female()
    assert audio._voice == "nova"


def test_audio_male_sets_onyx_voice():
    audio = Audio.of("Hello").male()
    assert audio._voice == "onyx"


def test_audio_voice_sets_explicit_voice():
    audio = Audio.of("Hello").voice("shimmer")
    assert audio._voice == "shimmer"


def test_audio_voice_overrides_previous_setting():
    audio = Audio.of("Hello").female().voice("echo")
    assert audio._voice == "echo"


def test_audio_model_override():
    audio = Audio.of("Hello").model("tts-1-hd")
    assert audio._model == "tts-1-hd"


def test_audio_speed_override():
    audio = Audio.of("Hello").speed(1.5)
    assert audio._speed == 1.5


def test_audio_format_override():
    audio = Audio.of("Hello").format("opus")
    assert audio._response_format == "opus"


def test_audio_chainable_methods_return_self():
    audio = Audio.of("Hello")
    assert audio.female() is audio
    assert audio.male() is audio
    assert audio.voice("alloy") is audio
    assert audio.model("tts-1") is audio
    assert audio.speed(1.0) is audio
    assert audio.format("mp3") is audio


# ─── Audio.generate() — mocked OpenAI call ───────────────────────────────────


def _fake_audio_bytes() -> bytes:
    return b"ID3\x03\x00"  # minimal MP3 magic


def _mock_openai_tts_response(data: bytes) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = data
    return mock_resp


@pytest.mark.asyncio
async def test_audio_generate_calls_tts_and_returns_response():
    audio_data = _fake_audio_bytes()
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(audio_data)

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        result = await Audio.of("Hello world").generate()

    assert isinstance(result, AudioResponse)
    assert result.data == audio_data
    mock_client.audio.speech.create.assert_called_once()


@pytest.mark.asyncio
async def test_audio_generate_passes_text_to_api():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hello world").generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["input"] == "Hello world"


@pytest.mark.asyncio
async def test_audio_generate_female_passes_nova_voice():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").female().generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["voice"] == "nova"


@pytest.mark.asyncio
async def test_audio_generate_male_passes_onyx_voice():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").male().generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["voice"] == "onyx"


@pytest.mark.asyncio
async def test_audio_generate_explicit_voice():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").voice("shimmer").generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["voice"] == "shimmer"


@pytest.mark.asyncio
async def test_audio_generate_passes_speed():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").speed(1.25).generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["speed"] == 1.25


@pytest.mark.asyncio
async def test_audio_generate_passes_format():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").format("opus").generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["response_format"] == "opus"


@pytest.mark.asyncio
async def test_audio_generate_hd_model():
    mock_client = MagicMock()
    mock_client.audio.speech.create.return_value = _mock_openai_tts_response(b"")

    with patch("fastapi_startkit.ai.audio.OpenAI", return_value=mock_client):
        await Audio.of("Hi").model("tts-1-hd").generate()

    call_kwargs = mock_client.audio.speech.create.call_args[1]
    assert call_kwargs["model"] == "tts-1-hd"


# ─── AudioResponse storage methods ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audio_response_store_writes_to_temp_when_no_storage():
    resp = AudioResponse(data=_fake_audio_bytes())

    path = await resp.store()

    assert os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read() == _fake_audio_bytes()
    os.remove(path)


@pytest.mark.asyncio
async def test_audio_response_store_as_uses_given_name():
    resp = AudioResponse(data=_fake_audio_bytes())

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/greeting.mp3"
        await resp.storeAs("greeting.mp3")

    mock_save.assert_called_once_with("greeting.mp3", "local")


@pytest.mark.asyncio
async def test_audio_response_store_publicly_as_uses_public_disk():
    resp = AudioResponse(data=_fake_audio_bytes())

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/greeting.mp3"
        await resp.storePubliclyAs("greeting.mp3")

    mock_save.assert_called_once_with("greeting.mp3", "public")


@pytest.mark.asyncio
async def test_audio_response_store_publicly_uses_public_disk():
    resp = AudioResponse(data=_fake_audio_bytes())

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/auto.mp3"
        await resp.storePublicly()

    _, disk = mock_save.call_args[0]
    assert disk == "public"


@pytest.mark.asyncio
async def test_audio_response_store_auto_filename_has_mp3_ext():
    resp = AudioResponse(data=_fake_audio_bytes(), fmt="mp3")

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/auto.mp3"
        await resp.store()

    name, _ = mock_save.call_args[0]
    assert name.endswith(".mp3")


@pytest.mark.asyncio
async def test_audio_response_store_uses_storage_facade_when_available():
    resp = AudioResponse(data=_fake_audio_bytes())

    mock_disk = MagicMock()

    with patch("fastapi_startkit.ai.audio.Storage") as mock_storage_cls:
        mock_storage_cls.disk.return_value = mock_disk
        await resp.storeAs("hello.mp3")

    mock_storage_cls.disk.assert_called_once_with("local")
    mock_disk.put.assert_called_once_with("hello.mp3", _fake_audio_bytes())

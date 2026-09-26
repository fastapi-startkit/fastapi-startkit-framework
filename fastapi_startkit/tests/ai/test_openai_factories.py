import base64
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi_startkit.ai.audio_factory import OpenAIAudioFactory
from fastapi_startkit.ai.image_factory import OpenAIImageFactory


def _openai_module(client: MagicMock) -> MagicMock:
    module = MagicMock()
    module.AsyncOpenAI.return_value = client
    return module


def _b64_image_response(data: bytes) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(b64_json=base64.b64encode(data).decode())]
    return response


class TestOpenAIImageFactory(IsolatedAsyncioTestCase):
    async def test_generate_decodes_b64_image_and_sends_quality_for_dalle3(self):
        client = MagicMock()
        client.images.generate = AsyncMock(return_value=_b64_image_response(b"png-bytes"))
        openai = _openai_module(client)

        with patch.dict("sys.modules", {"openai": openai}):
            result = await OpenAIImageFactory(api_key="k", base_url="u").generate(
                "A sunset", "1024x1024", "dall-e-3", "hd"
            )

        assert result == b"png-bytes"
        openai.AsyncOpenAI.assert_called_once_with(api_key="k", base_url="u")
        assert client.images.generate.call_args.kwargs["quality"] == "hd"

    async def test_generate_omits_quality_for_other_models(self):
        client = MagicMock()
        client.images.generate = AsyncMock(return_value=_b64_image_response(b"png"))

        with patch.dict("sys.modules", {"openai": _openai_module(client)}):
            await OpenAIImageFactory().generate("A cat", "512x512", "dall-e-2", "hd")

        assert "quality" not in client.images.generate.call_args.kwargs

    async def test_edit_sends_named_image_file_to_dalle2(self):
        client = MagicMock()
        client.images.edit = AsyncMock(return_value=_b64_image_response(b"edited"))

        with patch.dict("sys.modules", {"openai": _openai_module(client)}):
            result = await OpenAIImageFactory().edit("Add a hat", b"original", "1024x1024")

        assert result == b"edited"
        kwargs = client.images.edit.call_args.kwargs
        assert kwargs["model"] == "dall-e-2"
        assert kwargs["image"].name == "image.png"
        assert kwargs["image"].getvalue() == b"original"


class TestOpenAIAudioFactory(IsolatedAsyncioTestCase):
    async def test_synthesize_returns_speech_bytes(self):
        speech = MagicMock()
        speech.read.return_value = b"mp3-bytes"
        client = MagicMock()
        client.audio.speech.create = AsyncMock(return_value=speech)

        with patch.dict("sys.modules", {"openai": _openai_module(client)}):
            result = await OpenAIAudioFactory(api_key="k").synthesize("Hello", "nova", "tts-1", 1.25, "mp3")

        assert result == b"mp3-bytes"
        client.audio.speech.create.assert_awaited_once_with(
            model="tts-1", voice="nova", input="Hello", speed=1.25, response_format="mp3"
        )

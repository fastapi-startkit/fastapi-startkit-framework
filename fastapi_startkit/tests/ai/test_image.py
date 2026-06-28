"""Tests for the Image generation API (Image, ImageResponse, Document attachments)."""

from __future__ import annotations

import os
import tempfile
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi_startkit.ai import Document, Image, ImageResponse


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _fake_image_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n"  # minimal PNG magic


def _mock_provider(generate_result: bytes | None = None, edit_result: bytes | None = None) -> MagicMock:
    """Return a mock ImageFactory."""
    p = MagicMock()
    p.generate = AsyncMock(return_value=generate_result if generate_result is not None else _fake_image_bytes())
    p.edit = AsyncMock(return_value=edit_result if edit_result is not None else _fake_image_bytes())
    return p


# ─── Document used as image attachment ────────────────────────────────────────


class TestDocumentImageAttachment(IsolatedAsyncioTestCase):
    def test_document_from_path_reads_binary_via_to_bytes(self):
        """from_path auto-detects binary files and stores bytes content."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff")
            tmp_file = f.name
        try:
            doc = Document.from_path(tmp_file)
            assert doc.to_bytes() == b"\xff\xd8\xff"
        finally:
            os.remove(tmp_file)

    def test_document_content_bytes_stored_directly(self):
        doc = Document(content=b"\x89PNG", name="photo.png")
        assert doc.to_bytes() == b"\x89PNG"

    def test_document_content_str_encoded_to_bytes(self):
        doc = Document(content="hello", name="text.txt")
        assert doc.to_bytes() == b"hello"

    async def test_document_from_url_downloads_bytes(self):
        fake_data = b"fake-image-bytes"

        with patch("httpx.AsyncClient") as MockClient:
            mock_response = MagicMock()
            mock_response.content = fake_data
            mock_response.raise_for_status = MagicMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_response)

            doc = await Document.from_url("https://example.com/photo.jpg")

        assert doc.to_bytes() == fake_data
        assert doc.name == "photo.jpg"

    async def test_document_from_storage_reads_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_dir = os.path.join(tmp, "storage")
            os.makedirs(storage_dir)
            with open(os.path.join(storage_dir, "photo.jpg"), "wb") as f:
                f.write(b"\x89PNG")

            orig_dir = os.getcwd()
            os.chdir(tmp)
            try:
                with patch("fastapi_startkit.ai.document.Storage", None):
                    doc = await Document.from_storage("photo.jpg")
            finally:
                os.chdir(orig_dir)

        assert doc.to_bytes() == b"\x89PNG"

    def test_document_to_base64_encodes_bytes(self):
        import base64

        doc = Document(content=b"\x89PNG", name="photo.png")
        assert doc.to_base64() == base64.b64encode(b"\x89PNG").decode("utf-8")

    def test_document_to_base64_encodes_text(self):
        import base64

        doc = Document(content="hello", name="text.txt")
        assert doc.to_base64() == base64.b64encode(b"hello").decode("utf-8")


# ─── Image builder — chainable API ────────────────────────────────────────────


class TestImageBuilder(IsolatedAsyncioTestCase):
    def test_of_returns_image_instance(self):
        img = Image.of("A donut on a counter")
        assert isinstance(img, Image)
        assert img._prompt == "A donut on a counter"

    def test_landscape_sets_size(self):
        assert Image.of("test").landscape()._size == "1792x1024"

    def test_portrait_sets_size(self):
        assert Image.of("test").portrait()._size == "1024x1792"

    def test_square_sets_size(self):
        assert Image.of("test").landscape().square()._size == "1024x1024"

    def test_model_override(self):
        assert Image.of("test").model("dall-e-2")._model == "dall-e-2"

    def test_quality_override(self):
        assert Image.of("test").quality("hd")._quality == "hd"

    def test_attachments_sets_list(self):
        doc = Document(content=b"img", name="x.png")
        assert Image.of("test").attachments([doc])._attachments == [doc]


# ─── Image.generate() ─────────────────────────────────────────────────────────


class TestImageGeneration(IsolatedAsyncioTestCase):
    async def test_generate_calls_provider_and_returns_response(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            result = await Image.of("A donut on a counter").generate()

        assert isinstance(result, ImageResponse)
        assert result.data == _fake_image_bytes()
        provider.generate.assert_called_once()

    async def test_generate_passes_landscape_size_to_provider(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("test").landscape().generate()

        assert provider.generate.call_args[1]["size"] == "1792x1024"

    async def test_generate_passes_quality_to_provider(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("test").quality("hd").generate()

        assert provider.generate.call_args[1]["quality"] == "hd"

    async def test_generate_uses_edit_when_attachments_present(self):
        provider = _mock_provider()
        doc = Document(content=b"img-bytes", name="photo.png")

        with patch.object(Image, "_resolve_provider", return_value=provider):
            result = await Image.of("Make impressionist").attachments([doc]).generate()

        assert isinstance(result, ImageResponse)
        provider.edit.assert_called_once()
        provider.generate.assert_not_called()

    async def test_generate_passes_attachment_bytes_to_edit(self):
        provider = _mock_provider()
        doc = Document(content=b"raw-image-bytes", name="photo.png")

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("Make impressionist").attachments([doc]).generate()

        assert provider.edit.call_args[1]["image_bytes"] == b"raw-image-bytes"


# ─── ImageResponse storage methods ────────────────────────────────────────────


class TestImageResult(IsolatedAsyncioTestCase):
    async def test_store_writes_to_temp_when_no_storage(self):
        """Falls back to tempfile when Storage facade is unavailable."""
        resp = ImageResponse(data=_fake_image_bytes())

        path = await resp.store()

        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == _fake_image_bytes()
        os.remove(path)

    async def test_store_as_uses_given_name(self):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/result.png"
            path = await resp.storeAs("result.png")

        mock_save.assert_called_once_with("result.png", "local")
        assert path.endswith("result.png")

    async def test_store_publicly_as_uses_public_disk(self):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/result.png"
            await resp.storePubliclyAs("result.png")

        mock_save.assert_called_once_with("result.png", "public")

    async def test_store_publicly_uses_public_disk(self):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.png"
            await resp.storePublicly()

        _, disk = mock_save.call_args[0]
        assert disk == "public"

    async def test_store_auto_filename_has_png_ext(self):
        resp = ImageResponse(data=_fake_image_bytes(), fmt="png")

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.png"
            await resp.store()

        name, _ = mock_save.call_args[0]
        assert name.endswith(".png")

    async def test_store_uses_storage_facade_when_available(self):
        resp = ImageResponse(data=_fake_image_bytes())
        mock_disk = MagicMock()

        with patch("fastapi_startkit.ai.image.Storage") as mock_storage_cls:
            mock_storage_cls.disk.return_value = mock_disk
            await resp.storeAs("photo.png")

        mock_storage_cls.disk.assert_called_once_with("local")
        mock_disk.put.assert_called_once_with("photo.png", _fake_image_bytes())


# ─── GoogleImageFactory ───────────────────────────────────────────────────────


class TestGoogleImageFactory(IsolatedAsyncioTestCase):
    async def test_generate_calls_genai_and_returns_bytes(self):
        from fastapi_startkit.ai.image_factory import GoogleImageFactory

        fake_bytes = b"\x89PNG\r\n"
        mock_image = MagicMock()
        mock_image.image.image_bytes = fake_bytes
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]

        with patch.dict(
            "sys.modules",
            {"google": MagicMock(), "google.genai": MagicMock(), "google.genai.types": MagicMock()},
        ):
            with patch(
                "fastapi_startkit.ai.image_factory.asyncio.to_thread",
                new=AsyncMock(return_value=mock_response),
            ):
                provider = GoogleImageFactory(api_key="test-key")
                result = await provider.generate("A sunset", "1024x1024", "imagen-3.0-generate-002", "standard")

        assert result == fake_bytes

    def test_aspect_ratio_mapping(self):
        from fastapi_startkit.ai.image_factory import GoogleImageFactory

        provider = GoogleImageFactory()
        assert provider._ASPECT_MAP["1024x1024"] == "1:1"
        assert provider._ASPECT_MAP["1792x1024"] == "16:9"
        assert provider._ASPECT_MAP["1024x1792"] == "9:16"

    async def test_edit_raises_not_implemented(self):
        from fastapi_startkit.ai.image_factory import GoogleImageFactory

        provider = GoogleImageFactory(api_key="test-key")
        with self.assertRaisesRegex(NotImplementedError, "does not support image editing"):
            await provider.edit("Make it blue", b"\x89PNG", "1024x1024")

    async def test_image_builder_resolves_google_factory(self):
        mock_ai_config = MagicMock()
        mock_ai_config.default_image = "google"
        mock_ai_config.providers = {"google": MagicMock(key="gkey"), "openai": MagicMock(key="")}

        with patch("fastapi_startkit.ai.image.Config") as mock_config:
            mock_config.get.return_value = mock_ai_config
            from fastapi_startkit.ai.image_factory import GoogleImageFactory

            provider = Image.of("test")._resolve_provider()

        assert isinstance(provider, GoogleImageFactory)

"""Tests for the Image generation API (Image, ImageResponse, Document attachments)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi_startkit.ai.document import Document
from fastapi_startkit.ai.image import Image, ImageResponse


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def _fake_image_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n"  # minimal PNG magic


def _mock_provider(generate_result: bytes | None = None, edit_result: bytes | None = None) -> MagicMock:
    """Return a mock ImageGenerationProvider."""
    p = MagicMock()
    p.generate = AsyncMock(return_value=generate_result if generate_result is not None else _fake_image_bytes())
    p.edit = AsyncMock(return_value=edit_result if edit_result is not None else _fake_image_bytes())
    return p


# ─── Document used as image attachment ────────────────────────────────────────

class TestDocumentImageAttachment:
    def test_document_from_path_reads_binary_via_to_bytes(self, tmp_path):
        """from_path auto-detects binary files and stores bytes content."""
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        doc = Document.from_path(str(img))
        # Binary files: content is bytes, to_bytes() returns them directly
        assert doc.to_bytes() == b"\xff\xd8\xff"

    def test_document_content_bytes_stored_directly(self):
        doc = Document(content=b"\x89PNG", name="photo.png")
        assert doc.to_bytes() == b"\x89PNG"

    def test_document_content_str_encoded_to_bytes(self):
        doc = Document(content="hello", name="text.txt")
        assert doc.to_bytes() == b"hello"

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_document_from_storage_reads_bytes(self, tmp_path, monkeypatch):
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        (storage_dir / "photo.jpg").write_bytes(b"\x89PNG")
        monkeypatch.chdir(tmp_path)

        # Patch Storage so it falls back to the direct path read
        with patch("fastapi_startkit.ai.document.Storage", None):
            doc = await Document.from_storage("photo.jpg")

        assert doc.to_bytes() == b"\x89PNG"

    def test_document_to_base64_encodes_bytes(self):
        doc = Document(content=b"\x89PNG", name="photo.png")
        import base64
        assert doc.to_base64() == base64.b64encode(b"\x89PNG").decode("utf-8")

    def test_document_to_base64_encodes_text(self):
        doc = Document(content="hello", name="text.txt")
        import base64
        assert doc.to_base64() == base64.b64encode(b"hello").decode("utf-8")


# ─── Image builder — chainable API ────────────────────────────────────────────

class TestImageBuilder:
    def test_of_returns_image_instance(self):
        img = Image.of("A donut on a counter")
        assert isinstance(img, Image)
        assert img._prompt == "A donut on a counter"

    def test_landscape_sets_size(self):
        img = Image.of("test").landscape()
        assert img._size == "1792x1024"

    def test_portrait_sets_size(self):
        img = Image.of("test").portrait()
        assert img._size == "1024x1792"

    def test_square_sets_size(self):
        img = Image.of("test").landscape().square()
        assert img._size == "1024x1024"

    def test_model_override(self):
        img = Image.of("test").model("dall-e-2")
        assert img._model == "dall-e-2"

    def test_quality_override(self):
        img = Image.of("test").quality("hd")
        assert img._quality == "hd"

    def test_attachments_sets_list(self):
        doc = Document(content=b"img", name="x.png")
        img = Image.of("test").attachments([doc])
        assert img._attachments == [doc]


# ─── Image.generate() ─────────────────────────────────────────────────────────

class TestImageGeneration:
    @pytest.mark.asyncio
    async def test_generate_calls_provider_and_returns_response(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            result = await Image.of("A donut on a counter").generate()

        assert isinstance(result, ImageResponse)
        assert result.data == _fake_image_bytes()
        provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_passes_landscape_size_to_provider(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("test").landscape().generate()

        call_kwargs = provider.generate.call_args[1]
        assert call_kwargs["size"] == "1792x1024"

    @pytest.mark.asyncio
    async def test_generate_passes_quality_to_provider(self):
        provider = _mock_provider()

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("test").quality("hd").generate()

        call_kwargs = provider.generate.call_args[1]
        assert call_kwargs["quality"] == "hd"

    @pytest.mark.asyncio
    async def test_generate_uses_edit_when_attachments_present(self):
        provider = _mock_provider()
        doc = Document(content=b"img-bytes", name="photo.png")

        with patch.object(Image, "_resolve_provider", return_value=provider):
            result = await Image.of("Make impressionist").attachments([doc]).generate()

        assert isinstance(result, ImageResponse)
        provider.edit.assert_called_once()
        provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_passes_attachment_bytes_to_edit(self):
        provider = _mock_provider()
        doc = Document(content=b"raw-image-bytes", name="photo.png")

        with patch.object(Image, "_resolve_provider", return_value=provider):
            await Image.of("Make impressionist").attachments([doc]).generate()

        call_kwargs = provider.edit.call_args[1]
        assert call_kwargs["image_bytes"] == b"raw-image-bytes"


# ─── ImageResponse storage methods ────────────────────────────────────────────

class TestImageResult:
    @pytest.mark.asyncio
    async def test_store_writes_to_temp_when_no_storage(self):
        """Falls back to tempfile when Storage facade is unavailable."""
        resp = ImageResponse(data=_fake_image_bytes())

        path = await resp.store()

        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == _fake_image_bytes()
        os.remove(path)

    @pytest.mark.asyncio
    async def test_store_as_uses_given_name(self, tmp_path):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync", wraps=lambda name, disk: str(tmp_path / name)) as mock_save:
            path = await resp.storeAs("result.png")

        mock_save.assert_called_once_with("result.png", "local")
        assert path.endswith("result.png")

    @pytest.mark.asyncio
    async def test_store_publicly_as_uses_public_disk(self, tmp_path):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync", wraps=lambda name, disk: str(tmp_path / name)) as mock_save:
            await resp.storePubliclyAs("result.png")

        mock_save.assert_called_once_with("result.png", "public")

    @pytest.mark.asyncio
    async def test_store_publicly_uses_public_disk(self):
        resp = ImageResponse(data=_fake_image_bytes())

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.png"
            await resp.storePublicly()

        _, disk = mock_save.call_args[0]
        assert disk == "public"

    @pytest.mark.asyncio
    async def test_store_auto_filename_has_png_ext(self):
        resp = ImageResponse(data=_fake_image_bytes(), fmt="png")

        with patch.object(resp, "_save_sync") as mock_save:
            mock_save.return_value = "/tmp/auto.png"
            await resp.store()

        name, _ = mock_save.call_args[0]
        assert name.endswith(".png")

    @pytest.mark.asyncio
    async def test_store_uses_storage_facade_when_available(self):
        resp = ImageResponse(data=_fake_image_bytes())
        mock_disk = MagicMock()

        with patch("fastapi_startkit.ai.image.Storage") as mock_storage_cls:
            mock_storage_cls.disk.return_value = mock_disk
            await resp.storeAs("photo.png")

        mock_storage_cls.disk.assert_called_once_with("local")
        mock_disk.put.assert_called_once_with("photo.png", _fake_image_bytes())

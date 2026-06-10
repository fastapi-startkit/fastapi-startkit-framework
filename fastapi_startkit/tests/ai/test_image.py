"""Tests for the Image generation API (Image, ImageResponse, Files.Image)."""

from __future__ import annotations

import base64
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.ai.files import Files, ImageAttachment
from fastapi_startkit.ai.image import Image, ImageResponse


# ─── ImageAttachment via Files.Image ─────────────────────────────────────────


def test_files_image_from_path_reads_bytes(tmp_path):
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # minimal JPEG magic bytes

    attachment = Files.Image.fromPath(str(img))

    assert attachment.data == b"\xff\xd8\xff"
    assert attachment.name == "photo.jpg"


def test_files_image_from_storage_reads_from_storage_dir(tmp_path, monkeypatch):
    # Redirect "storage/" to a temp dir
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    (storage_dir / "photo.jpg").write_bytes(b"\x89PNG")

    monkeypatch.chdir(tmp_path)

    attachment = Files.Image.fromStorage("photo.jpg")

    assert attachment.data == b"\x89PNG"
    assert attachment.name == "photo.jpg"


def test_files_image_from_url_downloads_bytes():
    fake_data = b"fake-image-bytes"

    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = fake_data
        mock_open.return_value = mock_resp

        attachment = Files.Image.fromUrl("https://example.com/photo.jpg")

    assert attachment.data == fake_data
    assert attachment.name == "photo.jpg"


def test_image_attachment_to_base64():
    data = b"hello"
    att = ImageAttachment(data=data, name="test.png", media_type="image/png")
    assert att.to_base64() == base64.b64encode(b"hello").decode()


# ─── Image builder — chainable API ───────────────────────────────────────────


def test_image_of_returns_image_instance():
    img = Image.of("A donut on a counter")
    assert isinstance(img, Image)
    assert img._prompt == "A donut on a counter"


def test_image_landscape_sets_size():
    img = Image.of("test").landscape()
    assert img._size == "1792x1024"


def test_image_portrait_sets_size():
    img = Image.of("test").portrait()
    assert img._size == "1024x1792"


def test_image_square_sets_size():
    img = Image.of("test").landscape().square()
    assert img._size == "1024x1024"


def test_image_model_override():
    img = Image.of("test").model("dall-e-2")
    assert img._model == "dall-e-2"


def test_image_quality_override():
    img = Image.of("test").quality("hd")
    assert img._quality == "hd"


def test_image_attachments_sets_list():
    att = ImageAttachment(data=b"img", name="x.png")
    img = Image.of("test").attachments([att])
    assert img._attachments == [att]


# ─── Image.generate() — mocked OpenAI call ───────────────────────────────────


def _fake_image_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n"  # minimal PNG magic


def _b64_png() -> str:
    return base64.b64encode(_fake_image_bytes()).decode()


def _mock_openai_images_generate(b64: str):
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=b64)]
    return mock_response


@pytest.mark.asyncio
async def test_image_generate_calls_dalle_and_returns_response():
    b64 = _b64_png()
    mock_client = MagicMock()
    mock_client.images.generate.return_value = _mock_openai_images_generate(b64)

    with patch("fastapi_startkit.ai.image.OpenAI", return_value=mock_client):
        img_builder = Image.of("A donut on a counter")
        result = await img_builder.generate()

    assert isinstance(result, ImageResponse)
    assert result.data == _fake_image_bytes()
    mock_client.images.generate.assert_called_once()


@pytest.mark.asyncio
async def test_image_generate_passes_landscape_size():
    b64 = _b64_png()
    mock_client = MagicMock()
    mock_client.images.generate.return_value = _mock_openai_images_generate(b64)

    with patch("fastapi_startkit.ai.image.OpenAI", return_value=mock_client):
        await Image.of("test").landscape().generate()

    call_kwargs = mock_client.images.generate.call_args[1]
    assert call_kwargs["size"] == "1792x1024"


@pytest.mark.asyncio
async def test_image_generate_passes_quality_when_dalle3():
    b64 = _b64_png()
    mock_client = MagicMock()
    mock_client.images.generate.return_value = _mock_openai_images_generate(b64)

    with patch("fastapi_startkit.ai.image.OpenAI", return_value=mock_client):
        await Image.of("test").quality("hd").generate()

    call_kwargs = mock_client.images.generate.call_args[1]
    assert call_kwargs["quality"] == "hd"


@pytest.mark.asyncio
async def test_image_generate_uses_edit_when_attachments_present():
    b64 = _b64_png()
    mock_client = MagicMock()
    mock_client.images.edit.return_value = _mock_openai_images_generate(b64)

    att = ImageAttachment(data=b"img-bytes", name="photo.png")

    with patch("fastapi_startkit.ai.image.OpenAI", return_value=mock_client):
        result = await Image.of("Make impressionist").attachments([att]).generate()

    assert isinstance(result, ImageResponse)
    mock_client.images.edit.assert_called_once()
    mock_client.images.generate.assert_not_called()


# ─── ImageResponse storage methods ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_image_response_store_writes_to_temp_when_no_storage():
    """Falls back to tempfile when Storage facade is unavailable."""
    resp = ImageResponse(data=_fake_image_bytes())

    path = await resp.store()

    assert os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read() == _fake_image_bytes()
    os.remove(path)


@pytest.mark.asyncio
async def test_image_response_store_as_uses_given_name(tmp_path):
    resp = ImageResponse(data=_fake_image_bytes())

    with patch.object(resp, "_save_sync", wraps=lambda name, disk: str(tmp_path / name)) as mock_save:
        path = await resp.storeAs("result.png")

    mock_save.assert_called_once_with("result.png", "local")
    assert path.endswith("result.png")


@pytest.mark.asyncio
async def test_image_response_store_publicly_as_uses_public_disk(tmp_path):
    resp = ImageResponse(data=_fake_image_bytes())

    with patch.object(resp, "_save_sync", wraps=lambda name, disk: str(tmp_path / name)) as mock_save:
        await resp.storePubliclyAs("result.png")

    mock_save.assert_called_once_with("result.png", "public")


@pytest.mark.asyncio
async def test_image_response_store_publicly_uses_public_disk():
    resp = ImageResponse(data=_fake_image_bytes())

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/auto.png"
        await resp.storePublicly()

    _, disk = mock_save.call_args[0]
    assert disk == "public"


@pytest.mark.asyncio
async def test_image_response_store_auto_filename_has_png_ext():
    resp = ImageResponse(data=_fake_image_bytes(), fmt="png")

    with patch.object(resp, "_save_sync") as mock_save:
        mock_save.return_value = "/tmp/auto.png"
        await resp.store()

    name, _ = mock_save.call_args[0]
    assert name.endswith(".png")


@pytest.mark.asyncio
async def test_image_response_uses_storage_facade_when_available(tmp_path):
    resp = ImageResponse(data=_fake_image_bytes())

    mock_disk = MagicMock()

    with patch("fastapi_startkit.ai.image.Storage") as mock_storage_cls:
        mock_storage_cls.disk.return_value = mock_disk
        await resp.storeAs("photo.png")

    mock_storage_cls.disk.assert_called_once_with("local")
    mock_disk.put.assert_called_once_with("photo.png", _fake_image_bytes())

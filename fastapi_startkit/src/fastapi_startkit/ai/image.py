"""Image generation API — text-to-image and image editing via OpenAI DALL-E."""

from __future__ import annotations

import asyncio
import base64
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .files import ImageAttachment

# Optional runtime dependencies — imported at module level so tests can patch them.
try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment,misc]

try:
    from fastapi_startkit.storage.storage import Storage
except Exception:  # pragma: no cover
    Storage = None  # type: ignore[assignment,misc]


class ImageResponse:
    """Returned by :meth:`Image.generate`.

    Holds raw PNG bytes and provides async helpers to persist the image to
    any configured storage disk::

        image = await Image.of("A donut on a counter").generate()

        path = await image.store()                    # auto-named, private disk
        path = await image.storeAs("result.png")      # named, private disk
        path = await image.storePublicly()            # auto-named, public disk
        path = await image.storePubliclyAs("result.png")
    """

    def __init__(self, data: bytes, fmt: str = "png"):
        self._data = data
        self._fmt = fmt

    @property
    def data(self) -> bytes:
        """Raw image bytes."""
        return self._data

    def _auto_filename(self) -> str:
        return f"{uuid.uuid4()}.{self._fmt}"

    # ── Storage helpers ────────────────────────────────────────────────────────

    async def store(self) -> str:
        """Save to the default private disk with an auto-generated filename.

        Returns the filename (or full path when the Storage facade is not
        configured).
        """
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


class Image:
    """Fluent builder for image generation and editing.

    Usage — text to image::

        image = await Image.of("A donut on a counter").generate()

    Usage — edit with attachments::

        from fastapi_startkit.ai import Files

        image = await (
            Image.of("Make this impressionist")
            .attachments([
                Files.Image.fromStorage("photo.jpg"),
                Files.Image.fromPath("/tmp/photo.jpg"),
                Files.Image.fromUrl("https://example.com/photo.jpg"),
            ])
            .landscape()
            .generate()
        )
    """

    # DALL-E 3 size presets
    _LANDSCAPE_SIZE = "1792x1024"
    _PORTRAIT_SIZE = "1024x1792"
    _SQUARE_SIZE = "1024x1024"

    def __init__(self, prompt: str):
        self._prompt = prompt
        self._attachments: list[ImageAttachment] = []
        self._size: str = self._SQUARE_SIZE
        self._model: str = "dall-e-3"
        self._quality: str = "standard"
        self._n: int = 1

    @classmethod
    def of(cls, prompt: str) -> "Image":
        """Create an :class:`Image` builder with the given prompt."""
        return cls(prompt)

    # ── Modifier methods (chainable) ───────────────────────────────────────────

    def attachments(self, files: list) -> "Image":
        """Attach images for an editing request (switches to ``images.edit``)."""
        self._attachments = list(files)
        return self

    def landscape(self) -> "Image":
        """Use landscape size (1792×1024). DALL-E 3 only."""
        self._size = self._LANDSCAPE_SIZE
        return self

    def portrait(self) -> "Image":
        """Use portrait size (1024×1792). DALL-E 3 only."""
        self._size = self._PORTRAIT_SIZE
        return self

    def square(self) -> "Image":
        """Use square size (1024×1024)."""
        self._size = self._SQUARE_SIZE
        return self

    def model(self, name: str) -> "Image":
        """Override the model (default: ``dall-e-3``)."""
        self._model = name
        return self

    def quality(self, q: str) -> "Image":
        """Set quality — ``'standard'`` or ``'hd'`` (DALL-E 3 only)."""
        self._quality = q
        return self

    # ── Generation ─────────────────────────────────────────────────────────────

    async def generate(self) -> ImageResponse:
        """Call the API and return an :class:`ImageResponse`."""
        return await asyncio.to_thread(self._generate_sync)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _generate_sync(self) -> ImageResponse:
        if self._attachments:
            return self._edit()
        return self._create()

    def _resolve_api_key(self) -> Optional[str]:
        try:
            from fastapi_startkit.facades.Config import Config  # noqa: PLC0415

            ai_config = Config.get("ai")
            return ai_config.providers["openai"].key or None
        except Exception:
            return None

    def _create(self) -> ImageResponse:
        """Generate a new image from a text prompt."""
        client = OpenAI(api_key=self._resolve_api_key())
        params: dict = {
            "model": self._model,
            "prompt": self._prompt,
            "size": self._size,
            "n": self._n,
            "response_format": "b64_json",
        }
        if self._model == "dall-e-3":
            params["quality"] = self._quality

        response = client.images.generate(**params)
        b64 = response.data[0].b64_json
        data = base64.b64decode(b64)
        return ImageResponse(data=data, fmt="png")

    def _edit(self) -> ImageResponse:
        """Edit an existing image using the provided attachments.

        Only ``dall-e-2`` supports image editing; size is clamped to
        ``1024×1024`` since that is the only edit-supported size.
        """
        import io  # noqa: PLC0415

        client = OpenAI(api_key=self._resolve_api_key())

        main = self._attachments[0]
        image_file = io.BytesIO(main.data)
        image_file.name = main.name or "image.png"

        params: dict = {
            "model": "dall-e-2",
            "image": image_file,
            "prompt": self._prompt,
            "size": "1024x1024",
            "n": self._n,
            "response_format": "b64_json",
        }

        if len(self._attachments) > 1:
            mask = self._attachments[1]
            mask_file = io.BytesIO(mask.data)
            mask_file.name = mask.name or "mask.png"
            params["mask"] = mask_file

        response = client.images.edit(**params)
        b64 = response.data[0].b64_json
        data = base64.b64decode(b64)
        return ImageResponse(data=data, fmt="png")

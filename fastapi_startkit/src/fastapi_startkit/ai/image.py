"""Image generation API — text-to-image and image editing via a pluggable provider."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .document import Document
    from .image_factory import ImageFactory

try:
    from fastapi_startkit.storage.storage import Storage
except Exception:  # pragma: no cover
    Storage = None  # type: ignore[assignment,misc]

try:
    from fastapi_startkit import Config
except Exception:  # pragma: no cover
    Config = None  # type: ignore[assignment,misc]


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


class Image:
    """Fluent builder for image generation and editing.

    The active backend is selected from :attr:`~fastapi_startkit.ai.AIConfig.default_image`
    (env: ``AI_IMAGE_PROVIDER``). Defaults to OpenAI DALL-E.

    Usage — text to image::

        image = await Image.of("A donut on a counter").generate()

    Usage — edit with :class:`~fastapi_startkit.ai.Document` attachments::

        from fastapi_startkit.ai import Document

        image = await (
            Image.of("Make this impressionist")
            .attachments([await Document.from_url("https://example.com/photo.jpg")])
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
        self._attachments: list[Document] = []
        self._size: str = self._SQUARE_SIZE
        self._model: str = "dall-e-3"
        self._quality: str = "standard"

    @classmethod
    def of(cls, prompt: str) -> "Image":
        """Create an :class:`Image` builder with the given prompt."""
        return cls(prompt)

    # ── Modifier methods (chainable) ───────────────────────────────────────────

    def attachments(self, docs: list) -> "Image":
        """Attach :class:`~fastapi_startkit.ai.Document` objects for an editing request."""
        self._attachments = list(docs)
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
        """Call the configured image provider and return an :class:`ImageResponse`."""
        provider = self._resolve_provider()

        if self._attachments:
            image_bytes = await provider.edit(
                prompt=self._prompt,
                image_bytes=self._attachments[0].to_bytes(),
                size=self._size,
            )
        else:
            image_bytes = await provider.generate(
                prompt=self._prompt,
                size=self._size,
                model=self._model,
                quality=self._quality,
            )

        return ImageResponse(data=image_bytes, fmt="png")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _resolve_provider(self) -> "ImageFactory":
        from .image_factory import (  # noqa: PLC0415
            GoogleImageFactory,
            OpenAIImageFactory,
            StabilityImageFactory,
        )

        provider_name = "openai"
        api_key: Optional[str] = None
        base_url: Optional[str] = None
        google_key: Optional[str] = None

        try:
            ai_config = Config.get("ai") if Config is not None else None  # type: ignore[union-attr]
            if ai_config is None:
                raise RuntimeError("Config not available")
            provider_name = ai_config.default_image
            openai_cfg = ai_config.providers.get("openai")
            if openai_cfg:
                api_key = openai_cfg.key or None
                base_url = openai_cfg.url or None
            google_cfg = ai_config.providers.get("google")
            if google_cfg:
                google_key = google_cfg.key or None
        except Exception:
            pass

        if provider_name == "openai":
            return OpenAIImageFactory(api_key=api_key, base_url=base_url)
        if provider_name == "google":
            return GoogleImageFactory(api_key=google_key)
        if provider_name == "stability":
            return StabilityImageFactory()
        raise ValueError(f"Unknown image provider: {provider_name!r}. Use 'openai', 'google', or 'stability'.")

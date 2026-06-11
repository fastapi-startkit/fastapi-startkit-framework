"""Image generation provider abstractions.

Providers implement the :class:`ImageGenerationProvider` ABC so that the
:class:`~fastapi_startkit.ai.Image` builder is not hard-wired to a single
vendor.  Select the active provider via ``AI_IMAGE_PROVIDER`` in your
``.env`` (or ``AIConfig.image_provider``).

Supported providers
-------------------
* ``openai``     — OpenAI DALL-E 3 / DALL-E 2 (default)
* ``stability``  — Stability AI (stub, raises :exc:`NotImplementedError`)
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod


class ImageGenerationProvider(ABC):
    """Abstract base for image generation backends."""

    @abstractmethod
    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        """Generate a new image from a text prompt and return raw PNG bytes."""

    @abstractmethod
    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        """Edit an existing image (described by *image_bytes*) and return raw PNG bytes."""


class OpenAIImageProvider(ImageGenerationProvider):
    """OpenAI DALL-E provider using :class:`openai.AsyncOpenAI`.

    Uses DALL-E 3 for generation and DALL-E 2 for editing (the only model
    that supports inpainting as of mid-2025).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url

    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        params: dict = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        if model == "dall-e-3":
            params["quality"] = quality

        response = await client.images.generate(**params)
        return base64.b64decode(response.data[0].b64_json)

    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        import io  # noqa: PLC0415

        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        image_file = io.BytesIO(image_bytes)
        image_file.name = "image.png"

        response = await client.images.edit(
            model="dall-e-2",
            image=image_file,
            prompt=prompt,
            size="1024x1024",
            n=1,
            response_format="b64_json",
        )
        return base64.b64decode(response.data[0].b64_json)


class StabilityImageProvider(ImageGenerationProvider):
    """Stability AI provider stub — raises :exc:`NotImplementedError` until implemented."""

    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        raise NotImplementedError("StabilityImageProvider is not yet implemented")

    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        raise NotImplementedError("StabilityImageProvider is not yet implemented")

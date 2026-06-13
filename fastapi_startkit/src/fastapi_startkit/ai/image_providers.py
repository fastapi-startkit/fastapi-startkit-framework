"""Image generation provider abstractions.

Providers implement the :class:`ImageFactory` ABC so that the
:class:`~fastapi_startkit.ai.Image` builder is not hard-wired to a single
vendor.  Select the active provider via ``AI_IMAGE_PROVIDER`` in your
``.env`` (or ``AIConfig.image_provider``).

Supported providers
-------------------
* ``openai``     — OpenAI DALL-E 3 / DALL-E 2 (default)
* ``google``     — Google Imagen 3 via the ``google-genai`` SDK
* ``stability``  — Stability AI (stub, raises :exc:`NotImplementedError`)
"""

from __future__ import annotations

import asyncio
import base64
from abc import ABC, abstractmethod


class ImageFactory(ABC):
    """Abstract base for image generation backends."""

    @abstractmethod
    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        """Generate a new image from a text prompt and return raw PNG bytes."""

    @abstractmethod
    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        """Edit an existing image (described by *image_bytes*) and return raw PNG bytes."""


class OpenAIImageProvider(ImageFactory):
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


class GoogleImageProvider(ImageFactory):
    """Google Imagen 3 provider via the ``google-genai`` SDK.

    Requires: ``pip install google-genai``

    Configure via ``.env``::

        AI_IMAGE_PROVIDER=google
        GEMINI_API_KEY=your-key        # or GOOGLE_API_KEY

    Default model: ``imagen-3.0-generate-002``.
    Override with :meth:`~fastapi_startkit.ai.Image.model`::

        image = await Image.of("A sunset").model("imagen-3.0-fast-generate-001").generate()

    Size mapping (DALL-E pixel sizes → Imagen aspect ratios):

    +--------------+-----------+
    | Size string  | Ratio     |
    +==============+===========+
    | 1024×1024    | 1:1       |
    | 1792×1024    | 16:9      |
    | 1024×1792    | 9:16      |
    +--------------+-----------+
    """

    # Map DALL-E-style pixel sizes to Imagen aspect ratios
    _ASPECT_MAP: dict[str, str] = {
        "1024x1024": "1:1",
        "1792x1024": "16:9",
        "1024x1792": "9:16",
        "1280x720": "16:9",
        "720x1280": "9:16",
    }

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        """Generate an image via Imagen 3 and return raw PNG bytes."""
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        client = genai.Client(api_key=self._api_key)
        aspect_ratio = self._ASPECT_MAP.get(size, "1:1")

        response = await asyncio.to_thread(
            client.models.generate_images,
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
            ),
        )
        return response.generated_images[0].image.image_bytes

    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        """Image editing is not yet supported by :class:`GoogleImageProvider`.

        Use :class:`OpenAIImageProvider` for editing workflows.
        """
        raise NotImplementedError(
            "GoogleImageProvider does not support image editing yet. "
            "Use OpenAIImageProvider (AI_IMAGE_PROVIDER=openai) for editing."
        )


class StabilityImageProvider(ImageFactory):
    """Stability AI provider stub — raises :exc:`NotImplementedError` until implemented."""

    async def generate(self, prompt: str, size: str, model: str, quality: str) -> bytes:
        raise NotImplementedError("StabilityImageProvider is not yet implemented")

    async def edit(self, prompt: str, image_bytes: bytes, size: str) -> bytes:
        raise NotImplementedError("StabilityImageProvider is not yet implemented")

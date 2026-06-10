"""Files helpers — image attachment factories for use with Image editing requests."""

from __future__ import annotations

import base64
import os


class ImageAttachment:
    """Represents an image file to attach to an Image editing request.

    Instances are created via the :class:`Files.Image` factory, not directly::

        attachment = Files.Image.fromPath("/tmp/photo.jpg")
        attachment = Files.Image.fromStorage("photo.jpg")
        attachment = Files.Image.fromUrl("https://example.com/photo.jpg")
    """

    def __init__(
        self,
        data: bytes,
        name: str = "",
        media_type: str = "image/jpeg",
    ):
        self._data = data
        self._name = name
        self._media_type = media_type

    @property
    def data(self) -> bytes:
        """Raw bytes of the image."""
        return self._data

    @property
    def name(self) -> str:
        """Filename hint (basename of the source path or URL)."""
        return self._name

    @property
    def media_type(self) -> str:
        """MIME type of the image (e.g. ``image/jpeg``)."""
        return self._media_type

    def to_base64(self) -> str:
        """Return the image data base64-encoded as a plain string."""
        return base64.b64encode(self._data).decode("utf-8")


class Files:
    """Namespace for file attachment helpers.

    Usage::

        from fastapi_startkit.ai import Files, Image

        image = await (
            Image.of("Make this impressionist")
            .attachments([
                Files.Image.fromStorage("photo.jpg"),
                Files.Image.fromPath("/tmp/photo.jpg"),
                Files.Image.fromUrl("https://example.com/photo.jpg"),
            ])
            .generate()
        )
    """

    class Image:
        """Factory for :class:`ImageAttachment` objects.

        All methods are static — no need to instantiate ``Files.Image``.
        """

        @staticmethod
        def fromStorage(key: str) -> ImageAttachment:
            """Load an image from application storage (``storage/<key>``)."""
            path = os.path.join("storage", key)
            with open(path, "rb") as f:
                data = f.read()
            return ImageAttachment(data=data, name=key)

        @staticmethod
        def fromPath(path: str) -> ImageAttachment:
            """Load an image from a local filesystem path."""
            with open(path, "rb") as f:
                data = f.read()
            return ImageAttachment(data=data, name=os.path.basename(path))

        @staticmethod
        def fromUrl(url: str) -> ImageAttachment:
            """Download an image from a URL and return an :class:`ImageAttachment`.

            Uses :mod:`urllib.request` — no extra dependencies required.
            """
            import urllib.request

            with urllib.request.urlopen(url) as response:  # noqa: S310
                data = response.read()
            name = url.rstrip("/").split("/")[-1]
            return ImageAttachment(data=data, name=name)

"""Document helper — attach files, images, or text to agent prompts."""

from __future__ import annotations

import asyncio
import base64

# Optional runtime dependency — imported at module level so tests can patch it.
try:
    from fastapi_startkit.storage.storage import Storage
except Exception:  # pragma: no cover
    Storage = None  # type: ignore[assignment,misc]


class Document:
    """Attach text or binary content to :meth:`~fastapi_startkit.ai.Agent.prompt` calls.

    Supports both text (for LLM context documents) and binary (for image
    attachments sent to :class:`~fastapi_startkit.ai.Image`).

    Text::

        doc = Document.from_path("report.txt")
        agent.prompt("Summarise this", attachments=[doc])

    Binary image::

        doc = await Document.from_url("https://example.com/photo.jpg")
        image = await Image.of("Make this impressionist").attachments([doc]).generate()
    """

    def __init__(self, content: str | bytes, name: str = "", media_type: str = "text/plain"):
        self.content = content
        self.name = name
        self.media_type = media_type

    # ── Sync constructors (text) ───────────────────────────────────────────────

    @classmethod
    def from_path(cls, path: str) -> "Document":
        """Load a document from a local file path.

        Text files are returned with ``str`` content; binary files
        (e.g. images) fall back to ``bytes`` automatically.
        """
        try:
            with open(path) as f:
                content: str | bytes = f.read()
        except UnicodeDecodeError:
            with open(path, "rb") as f:
                content = f.read()
        return cls(content=content, name=path)

    # ── Async constructors (binary) ────────────────────────────────────────────

    @classmethod
    async def from_storage(cls, key: str) -> "Document":
        """Load a binary file from application storage (``storage/<key>``) asynchronously.

        Falls back to reading directly from the ``storage/`` directory relative
        to the current working directory if the Storage facade is not configured.
        """

        def _read() -> bytes:
            if Storage is not None:
                try:
                    disk = Storage.disk("local")
                    # Resolve the full path and read as binary
                    resolved_path = disk.get_path(key)
                    with open(resolved_path, "rb") as f:
                        return f.read()
                except Exception:
                    pass
            import os  # noqa: PLC0415

            with open(os.path.join("storage", key), "rb") as f:
                return f.read()

        data = await asyncio.to_thread(_read)
        return cls(content=data, name=key)

    @classmethod
    async def from_url(cls, url: str) -> "Document":
        """Download bytes from a URL asynchronously using *httpx*.

        Example::

            doc = await Document.from_url("https://example.com/photo.jpg")
        """
        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
        name = url.rstrip("/").split("/")[-1]
        return cls(content=response.content, name=name)

    # ── Binary accessor ────────────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        """Return the document content as raw bytes.

        If the content was loaded as text (e.g. via :meth:`from_path`),
        it is UTF-8 encoded. Binary content is returned as-is.
        """
        if isinstance(self.content, bytes):
            return self.content
        return self.content.encode("utf-8")

    def to_base64(self) -> str:
        """Return the document content base64-encoded as a plain string.

        Useful when an API expects a base64-encoded image or audio payload::

            doc = Document.from_path("/tmp/photo.jpg")
            encoded = doc.to_base64()
        """
        return base64.b64encode(self.to_bytes()).decode("utf-8")

    # ── LLM content blocks ─────────────────────────────────────────────────────

    def to_anthropic_block(self) -> dict:
        """Return an Anthropic-compatible content block for this document."""
        return {
            "type": "document",
            "source": {
                "type": "text",
                "media_type": self.media_type,
                "data": self.content,
            },
            "title": self.name,
        }

    def to_openai_block(self) -> dict:
        """Return an OpenAI-compatible content block for this document."""
        return {
            "type": "text",
            "text": f"[Document: {self.name}]\n{self.content}",
        }

    def to_langchain_block(self) -> dict:
        """Return a LangChain content block for this document.

        Text (or ``text/*`` media) is inlined as a labelled text part; everything
        else becomes a base64 ``image``/``file`` block the model reads natively.
        """
        is_text = isinstance(self.content, str) or self.media_type.startswith("text/")
        if is_text:
            text = self.content if isinstance(self.content, str) else self.content.decode("utf-8", "replace")
            return {"type": "text", "text": f"[Document: {self.name}]\n{text}"}
        block_type = "image" if self.media_type.startswith("image/") else "file"
        return {"type": block_type, "base64": self.to_base64(), "mime_type": self.media_type}

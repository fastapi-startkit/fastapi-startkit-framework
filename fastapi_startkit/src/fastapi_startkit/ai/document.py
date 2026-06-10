"""Document helper — attach files or text to agent prompts."""

from __future__ import annotations


class Document:
    """Attach documents to agent.prompt() calls."""

    def __init__(self, content: str, name: str = "", media_type: str = "text/plain"):
        self.content = content
        self.name = name
        self.media_type = media_type

    @classmethod
    def from_path(cls, path: str) -> "Document":
        """Load a document from a local file path."""
        with open(path) as f:
            content = f.read()
        return cls(content=content, name=path)

    @classmethod
    def from_storage(cls, key: str) -> "Document":
        """Load a document from application storage (storage/<key>)."""
        return cls.from_path(f"storage/{key}")

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

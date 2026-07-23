from pydantic import BaseModel

from fastapi_startkit.mcp import Tool, Response


class EchoInput(BaseModel):
    message: str


class EchoTool(Tool):
    """Return the caller's message unchanged — useful for connectivity checks."""

    name = "echo"
    description = "Echo the provided message back to the caller."

    def schema(self):
        return EchoInput

    async def handle(self, arguments: dict) -> Response:
        message = arguments.get("message", "")
        return Response.text(message)


class WordCountInput(BaseModel):
    text: str


class WordCountOutput(BaseModel):
    words: int
    characters: int
    lines: int


class WordCountTool(Tool):
    """Count words, characters, and lines in a block of text."""

    name = "word_count"
    description = "Count the number of words, characters, and lines in a piece of text."

    def schema(self):
        return WordCountInput

    def output_schema(self):
        return WordCountOutput

    async def handle(self, arguments: dict) -> Response:
        text: str = arguments.get("text", "")
        stats = {
            "words": len(text.split()) if text.strip() else 0,
            "characters": len(text),
            "lines": len(text.splitlines()) if text else 0,
        }
        return Response.structure(stats)

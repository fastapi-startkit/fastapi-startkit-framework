"""Dev-tools MCP server example.

Demonstrates a practical MCP server with tools, a prompt, and a resource.

Run with:
    uv run uvicorn app:app --reload
"""

import os
import textwrap
from pydantic import BaseModel

from fastapi_startkit.mcp import (
    Argument,
    Prompt,
    Resource,
    Response,
    Server,
    Tool,
)


# ── Tools ─────────────────────────────────────────────────────────────────────


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


# ── Prompt ────────────────────────────────────────────────────────────────────


class CodeReviewPrompt(Prompt):
    """Generate a code-review prompt for a given language."""

    name = "code_review"
    title = "Code Review"
    description = "Generates a structured code-review prompt for the specified programming language."

    def arguments(self):
        return [
            Argument(name="language", description="Programming language to review (e.g. Python, TypeScript)", required=True),
            Argument(name="focus", description="Optional focus area (e.g. security, performance, readability)", required=False),
        ]

    async def handle(self, arguments: dict) -> Response:
        language = arguments.get("language", "code")
        focus = arguments.get("focus", "")
        focus_line = f" Focus especially on {focus}." if focus else ""
        prompt_text = textwrap.dedent(f"""
            You are an expert {language} code reviewer.{focus_line}

            Please review the provided code and give structured feedback covering:
            1. Correctness — does the code do what it intends?
            2. Readability — is the code easy to understand and maintain?
            3. Performance — are there obvious inefficiencies?
            4. Security — are there any security concerns?
            5. Suggested improvements — concrete, actionable next steps.
        """).strip()
        return Response.text(prompt_text)


# ── Resource ──────────────────────────────────────────────────────────────────


class EnvResource(Resource):
    """Expose non-sensitive environment variables as a resource."""

    uri = "resource:///env"
    name = "environment"
    description = "A snapshot of selected non-sensitive environment variables."
    mime_type = "application/json"

    # Variables that are safe to expose
    _ALLOWED = {"PATH", "LANG", "TZ", "HOME", "USER", "SHELL", "TERM"}

    async def read(self, **kwargs) -> str:
        import json
        safe = {k: v for k, v in os.environ.items() if k in self._ALLOWED}
        return json.dumps(safe, indent=2)


# ── Server ────────────────────────────────────────────────────────────────────


class DevToolsServer(Server):
    """A developer-tools MCP server with echo, word-count, code-review, and env resources."""

    name = "dev-tools"
    description = "Developer utilities exposed as an MCP server."
    instructions = (
        "Use `echo` for connectivity checks, `word_count` to analyse text, "
        "and `code_review` to get a structured review prompt. "
        "Read the `environment` resource for runtime context."
    )

    def tools(self):
        return [EchoTool, WordCountTool]

    def prompts(self):
        return [CodeReviewPrompt]

    def resources(self):
        return [EnvResource]


# ── Application ───────────────────────────────────────────────────────────────

from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider

mcp_server = DevToolsServer()

app = Application(providers=[FastAPIProvider])
app.include_router(mcp_server.router(prefix="/mcp"))


@app.get("/")
async def index():
    return {"message": "Dev-Tools MCP server is running.", "mcp_endpoint": "/mcp"}

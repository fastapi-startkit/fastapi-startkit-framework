from fastapi_startkit.mcp import Server

from .tools import EchoTool, WordCountTool
from .prompts import CodeReviewPrompt
from .resources import EnvResource


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

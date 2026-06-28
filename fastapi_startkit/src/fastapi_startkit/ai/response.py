"""AgentResponse and AgentSnapshot — response containers for AI agents."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import Agent


@dataclass
class AgentResponse:
    """Returned by Agent.prompt(). Wraps the LLM response."""

    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: Any = None
    parsed: Any = None

    def text(self) -> str:
        """Return the text content."""
        return self.content

    def json(self) -> Any:
        """Parse the content as JSON."""
        return json.loads(self.content)

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


@dataclass
class AgentSnapshot:
    """
    Record-and-replay snapshot for testing.

    - If the file at ``path`` **does not exist**: the agent calls the real API,
      saves the response as JSON, then returns it.
    - If the file **exists**: the saved response is loaded and returned without
      hitting the API.

    Example::

        agent.fake({"*analyze*": AgentSnapshot(path="tests/fixtures/analysis.json")})
    """

    path: str

    def exists(self) -> bool:
        """Return True if the snapshot file is already recorded."""
        return os.path.exists(self.path)

    def load(self) -> AgentResponse:
        """Load the recorded response from disk."""
        with open(self.path) as f:
            data = json.load(f)
        return AgentResponse(
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls", []),
            usage=data.get("usage", {}),
        )

    def save(self, response: AgentResponse) -> None:
        """Persist a real API response to disk for future replays."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                {
                    "content": response.content,
                    "tool_calls": response.tool_calls,
                    "usage": response.usage,
                },
                f,
                indent=2,
            )

    async def resolve(self, agent: "Agent", message: str, **run_kwargs: Any) -> AgentResponse:
        """
        Return the response — from disk if recorded, or from the real API
        (which is then saved for future runs).
        """
        if self.exists():
            return self.load()
        response = await agent._run(message, **run_kwargs)
        self.save(response)
        return response

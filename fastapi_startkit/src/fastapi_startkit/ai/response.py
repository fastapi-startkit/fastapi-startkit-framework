from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import Agent


@dataclass
class AgentResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: Any = None
    parsed: Any = None
    runtime: float = 0.0

    @property
    def runtime_ms(self) -> float:
        return self.runtime * 1000

    def text(self) -> str:
        return self.content

    def json(self) -> Any:
        return json.loads(self.content)

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


@dataclass
class AgentSnapshot:

    path: str

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self) -> AgentResponse:
        with open(self.path) as f:
            data = json.load(f)
        return AgentResponse(
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls", []),
            usage=data.get("usage", {}),
            runtime=data.get("runtime", 0.0),
        )

    def save(self, response: AgentResponse) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                {
                    "content": response.content,
                    "tool_calls": response.tool_calls,
                    "usage": response.usage,
                    "runtime": response.runtime,
                },
                f,
                indent=2,
            )

    async def resolve(self, agent: "Agent", message: str, **run_kwargs: Any) -> AgentResponse:
        if self.exists():
            return self.load()
        response = await agent.prompt(message, **run_kwargs)
        self.save(response)
        return response

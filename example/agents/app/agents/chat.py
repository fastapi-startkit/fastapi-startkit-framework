from typing import Callable

from fastapi_startkit.ai import Agent, Middleware

from app.middleware.agent_logger import AgentLogger
from app.tools.job_search_tool import job_search_tool


class RouterAgent(Agent):
    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    def tools(self) -> list[Callable]:
        return [job_search_tool]

    def instructions(self) -> str:
        return "You are a friendly customer support assistant."

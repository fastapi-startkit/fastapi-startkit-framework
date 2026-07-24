from fastapi_startkit.ai import Agent, Middleware
from langchain_core.tools import BaseTool

from app.middleware.agent_logger import AgentLogger
from app.tools.job_search_tool import job_search_tool


class ChatAgent(Agent):
    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    def tools(self) -> list[BaseTool]:
        return [job_search_tool]

    def instructions(self) -> str:
        return "You are a friendly customer support assistant."

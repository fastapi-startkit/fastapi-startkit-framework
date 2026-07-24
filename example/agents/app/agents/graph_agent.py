from fastapi_startkit.ai import GraphAgent, GraphRunner, Middleware
from fastapi_startkit.ai.graph import AgentState
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer

from app.middleware.agent_logger import AgentLogger
from app.tools.job_search_tool import job_search_tool


class SalesAgent(GraphAgent):
    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    def tools(self) -> list[BaseTool]:
        return [job_search_tool]

    async def graph(self, runner: GraphRunner) -> StateGraph:
        from fastapi_startkit.application import app

        checkpointer: Checkpointer = await app().make("checkpointer")

        return (
            StateGraph(AgentState)
            .add_node("llm", runner.llm)
            .add_node("tools", runner.call_tools)
            .add_edge(START, "llm")
            .add_conditional_edges("llm", runner.route, ["tools", END])
            .add_edge("tools", "llm")
        ).compile(checkpointer=checkpointer)

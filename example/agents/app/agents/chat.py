from typing import Callable

from fastapi_startkit.ai import Agent, GraphAgent, Middleware

from app.middleware.agent_logger import AgentLogger
from app.tools.job_search_tool import job_search_tool


class RouterAgent(GraphAgent):
    def graph(self):
        graph = StateGraph(MessagesState)

        # Add nodes
        graph.add_node("llm_call", llm_call)
        graph.add_node("tool_node", tool_node)

        # Add edges to connect nodes
        graph.add_edge(START, "llm_call")
        graph.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
        graph.add_edge("tool_node", "llm_call")

        # Compile the agent
        agent = graph.compile()

    def middleware(self) -> list[Middleware]:
        return [AgentLogger()]

    def tools(self) -> list[Callable]:
        return [job_search_tool]

    def instructions(self) -> str:
        return "You are a friendly customer support assistant."

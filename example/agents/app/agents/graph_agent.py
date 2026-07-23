from fastapi_startkit.ai import GraphAgent, GraphRunner
from langgraph.graph import StateGraph


class SalesAgent(GraphAgent):
    def checkpointer(self):
        pass
    def graph(self, runner: GraphRunner) -> StateGraph:
        return StateGraph()

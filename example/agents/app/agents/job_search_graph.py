import json
from typing import cast

from fastapi_startkit.ai import state as ai_state
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.state import InputState, OutputState, OverallState, RouterOutput

# Stand-in for a real profile lookup; the router decides when it's needed.
USER_PROFILE = {
    "name": "Alice",
    "title": "Python Developer",
    "location": "Remote",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}


async def router_node(state: InputState, config: RunnableConfig) -> dict:
    """Context: only the user input. No history, no profile, no tool output.

    Handles greetings itself: for the 'chat' intent it answers inline via
    RouterOutput.reply, so no extra node/LLM call is needed.
    """
    from app.agents.agent import JobSearchRouterAgent

    response = await JobSearchRouterAgent(state, config).prompt(state["query"])
    decision = cast(
        RouterOutput, ai_state.structured(response) or RouterOutput.model_validate_json(ai_state.text(response))
    )

    out: dict = {"intent": decision.intent, "contexts": decision.contexts}
    if decision.intent == "chat":
        out |= {"type": "text", "data": decision.reply, "data_type": "string"}
    return out


def route(state: OverallState) -> str:
    # chat is already answered inline by the router; company_research isn't built yet.
    return "job_search" if state["intent"] == "job_search" else END


# --- job search ------------------------------------------------------------


async def job_search_node(state: OverallState, config: RunnableConfig) -> dict:
    """Context: the thread's history + the user profile — both owned by JobSearchAgent.

    Delegates the tool-calling loop to JobSearchAgent.prompt(), then pulls the raw job
    rows out of the response's tool_events (the summarizer node turns them into prose).
    Also reports the calls it made — {"name", "args"} — so they can be shown/persisted.
    """
    from app.agents.agent import JobSearchAgent

    response = await JobSearchAgent(state, config).prompt(state["query"])

    jobs: list[dict] = []
    calls: list[dict] = []
    for event in ai_state.tool_events(response):
        if event["name"] == "job_search_tool":
            jobs.extend(json.loads(event["content"]))
            calls.append({"name": event["name"], "args": event["args"]})

    return {"type": "tool_response", "data": jobs, "data_type": "json", "tool_calls": calls}


# --- ask user (human-in-the-loop) ------------------------------------------


def ask_user_node(state: OverallState) -> dict:
    """No jobs found: pause the graph and ask the frontend to refine the search.

    interrupt() freezes the run (state is persisted by the checkpointer) and
    surfaces this payload to the caller. The graph resumes when the caller sends
    Command(resume=<reply>), and interrupt() returns that reply here.
    """
    from langgraph.types import interrupt

    reply = interrupt(
        {
            "type": "question",
            "reason": "no_jobs",
            "message": f"No jobs matched '{state['query']}'. Try different keywords, or send blank to stop.",
        }
    )

    return {"query": str(reply).strip(), "data": None}


def after_ask(state: OverallState) -> str:
    return "job_search" if state["query"] else "job_summarizer"


# --- job summarizer --------------------------------------------------------


async def job_summarizer_node(state: OverallState, config: RunnableConfig) -> dict:
    """Context: only the tool response. Never sees the query or the profile."""
    if not state["data"] and state["query"]:
        # ask_user still wants a refined query; don't spend a call summarizing nothing
        return {}

    from app.agents.agent import JobSummarizerAgent

    response = await JobSummarizerAgent(state, config).prompt(json.dumps(state["data"] or []))

    return {"type": "text", "data": ai_state.text(response), "data_type": "string"}


def ask_or_finish(state: OverallState) -> str:
    return "ask_user" if not state["data"] and state["query"] else END


def build() -> StateGraph:
    builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)

    builder.add_node("router", router_node)
    builder.add_node("job_search", job_search_node)
    builder.add_node("ask_user", ask_user_node)
    builder.add_node("job_summarizer", job_summarizer_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route, ["job_search", END])
    builder.add_edge("job_search", "job_summarizer")
    builder.add_conditional_edges("job_summarizer", ask_or_finish, ["ask_user", END])
    builder.add_conditional_edges("ask_user", after_ask, ["job_search", "job_summarizer"])

    return builder


_graph: CompiledStateGraph | None = None


async def job_graph() -> CompiledStateGraph:
    """Compile once, backed by the container's checkpointer (needed for interrupts)."""
    global _graph
    if _graph is None:
        from fastapi_startkit.application import app

        checkpointer = await app().make("checkpointer")
        _graph = build().compile(checkpointer=checkpointer)
    return _graph

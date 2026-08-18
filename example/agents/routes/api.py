import json
import uuid

from app.agents.job_search_graph import job_graph
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi_startkit.inertia import Inertia
from langgraph.types import Command

from app.models.message import Message
from app.models.thread import Thread
from app.requests.chat import ChatRequest

api = APIRouter()


@api.get("/")
async def index():
    # Job search is the default agent — land straight on its chat.
    return Inertia.render("chat/jobs/Index")


def _frames(event: dict) -> dict | None:
    """Map a StandardStreamEvent onto the flat SSE frame the frontend renders."""
    if event["event"] == "on_chat_model_stream" and (text := str(event["data"]["chunk"].text)):
        return {"type": "delta", "text": text}
    if event["event"] == "on_tool_end":
        output = event["data"].get("output")
        return {"type": "tool_response", "name": event["name"], "content": str(getattr(output, "content", output))}
    return None


@api.get("/jobs")
async def jobs_page():
    return Inertia.render("chat/jobs/Index")


@api.post("/jobs/stream")
async def jobs_stream(request: ChatRequest):
    graph = await job_graph()
    # turn_id groups every row this turn produces; RememberMixin stamps it as run_id.
    config = {"configurable": {"thread_id": request.thread_id, "turn_id": str(uuid.uuid4())}}

    def sse(frame: dict) -> str:
        return f"data: {json.dumps(frame)}\n\n"

    async def generate():
        # A pending interrupt on this thread means the last turn asked the user to
        # refine; this message is the reply, so resume. Otherwise it's a fresh query.
        snapshot = await graph.aget_state(config)
        payload = Command(resume=request.message) if snapshot.interrupts else {"query": request.message}

        # Each agent persists its own side of the turn (RememberMixin); the route only
        # stores what no agent owns: the user's message, before the run so agents can
        # tell history from the current turn, and the interrupt question after it.
        await Thread.first_or_create({"id": request.thread_id}, {"id": request.thread_id})
        await Message.create(
            {
                "thread_id": request.thread_id,
                "role": "user",
                "type": "text",
                "data": {"text": request.message},
                "data_type": "string",
                "run_id": None,
            }
        )

        streamed = False
        async for event in graph.astream_events(payload, config):
            node = (event.get("metadata") or {}).get("langgraph_node", "")

            # Surface each tool call as it's made — name + args — so the UI can show
            # "calling job_search_tool(...)" live, before its result envelope lands.
            if event["event"] == "on_tool_start":
                yield sse(
                    {
                        "kind": "tool_call",
                        "node": node,
                        "name": event["name"],
                        "args": event["data"].get("input") or {},
                    }
                )

            # Forward every tool_response envelope a node commits (job_search today,
            # company_research tomorrow) so the UI can render before the prose lands.
            if event["event"] == "on_chain_end" and node and event["name"] == node:
                out = event["data"].get("output") or {}
                if isinstance(out, dict) and out.get("type") == "tool_response":
                    yield sse({"kind": "envelope", "node": node, **out})

            # Stream every node's tokens, tagged with the node; the frontend decides
            # what to render (the router's are structured-output JSON, for instance).
            if event["event"] == "on_chat_model_stream":
                if (chunk := event["data"].get("chunk")) and (text := str(chunk.text)):
                    streamed = streamed or node != "router"
                    yield sse({"kind": "delta", "node": node, "text": text})

        snapshot = await graph.aget_state(config)
        if snapshot.interrupts:
            # No jobs -> the graph paused at ask_user; surface its question for the UI.
            question = snapshot.interrupts[0].value
            yield sse({"kind": "interrupt", **question})
            await Message.create(
                {
                    "thread_id": request.thread_id,
                    "role": "ai",
                    "type": "text",
                    "data": {"text": question["message"]},
                    "data_type": "string",
                    "run_id": config["configurable"]["turn_id"],
                    "meta": {"agent": "ask_user"},
                }
            )
        elif not streamed and snapshot.values.get("type") == "text":
            # Greeting answered inline by the router (not token-streamed) -> emit it whole.
            yield sse({"kind": "envelope", "type": "text", "data": snapshot.values.get("data") or "", "data_type": "string"})

    return StreamingResponse(generate(), media_type="text/event-stream")

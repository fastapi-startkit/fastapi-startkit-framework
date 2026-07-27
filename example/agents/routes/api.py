import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from fastapi_startkit.inertia import Inertia
from langgraph.types import Command

from app.agents.chat import ChatAgent
from app.agents.graph_agent import SalesAgent
from app.agents.job_search_graph import job_graph
from app.models.message import Message
from app.models.thread import Thread
from app.requests.chat import ChatRequest

api = APIRouter()


@api.get("/")
async def index(request: Request):
    return Inertia.render(
        "chat/Index",
        {
            "user": {"name": "Alice"},
        },
    )


@api.post("/chat")
async def chat(request: ChatRequest):
    response = await ChatAgent().prompt(request.message)
    return {"content": response.content}


@api.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        async for frame in ChatAgent().stream(request.message):
            yield f"data: {json.dumps(frame)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@api.post("/sales/stream")
async def sales_stream(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    async def generate():
        async for frame in SalesAgent().stream(request.message, config=config):
            yield f"data: {json.dumps(frame)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@api.get("/sales")
async def sales_page():
    return Inertia.render(
        "chat/sales/Index",
    )


@api.get("/jobs")
async def jobs_page():
    return Inertia.render("chat/jobs/Index")


@api.post("/jobs/stream")
async def jobs_stream(request: ChatRequest):
    graph = await job_graph()
    config = {"configurable": {"thread_id": request.thread_id}}

    def sse(frame: dict) -> str:
        return f"data: {json.dumps(frame)}\n\n"

    async def generate():
        # A pending interrupt on this thread means the last turn asked the user to
        # refine; this message is the reply, so resume. Otherwise it's a fresh query.
        snapshot = await graph.aget_state(config)
        payload = Command(resume=request.message) if snapshot.interrupts else {"query": request.message}

        run_id: str | None = None
        tool_rows: list[tuple[str, dict]] = []  # (node, row)
        streamed: list[str] = []
        reply_node = "ask_user"  # overwritten by whichever node actually speaks
        usage_by_node: dict[str, dict] = {}
        model_by_node: dict[str, str] = {}

        async for event in graph.astream_events(payload, config):
            run_id = run_id or event.get("run_id")
            node = (event.get("metadata") or {}).get("langgraph_node", "")

            # Token usage per node, from every LLM call the run makes (including the
            # buffered ones inside JobSearchAgent — their model events still surface).
            if event["event"] == "on_chat_model_end" and node:
                meta = getattr(event["data"].get("output"), "usage_metadata", None) or {}
                if meta:
                    totals = usage_by_node.setdefault(node, {"input": 0, "output": 0})
                    totals["input"] += meta.get("input_tokens", 0)
                    totals["output"] += meta.get("output_tokens", 0)
                if model_name := (event.get("metadata") or {}).get("ls_model_name"):
                    model_by_node[node] = model_name

            # Capture every node that commits a tool_response envelope (job_search today,
            # company_research tomorrow): downstream nodes overwrite state["data"], so the
            # raw rows only exist here. Forward them so the UI can render before the prose.
            if event["event"] == "on_chain_end" and node and event["name"] == node:
                out = event["data"].get("output") or {}
                if isinstance(out, dict) and out.get("type") == "tool_response":
                    rows = out.get("data") or []
                    calls = out.get("tool_calls") or []
                    for call in calls:
                        tool_rows.append((node, {"type": "tool_call", "data": call, "data_type": "json"}))
                    tool_rows.append((node, {"type": "tool_response", "data": rows, "data_type": "json"}))
                    yield sse(
                        {
                            "kind": "envelope",
                            "node": node,
                            "type": "tool_response",
                            "data": rows,
                            "data_type": "json",
                            "tool_calls": calls,
                        }
                    )

            if event["event"] != "on_chat_model_stream":
                continue
            # Stream every node's tokens, tagged with the node; the frontend decides
            # what to render (the router's are structured-output JSON, for instance).
            if (chunk := event["data"].get("chunk")) and (text := str(chunk.text)):
                if node != "router":  # persisted reply = user-facing text only
                    streamed.append(text)
                    reply_node = node
                yield sse({"kind": "delta", "node": node, "text": text})

        snapshot = await graph.aget_state(config)
        reply = "".join(streamed)
        if snapshot.interrupts:
            # No jobs -> the graph paused at ask_user; surface its question for the UI.
            reply = snapshot.interrupts[0].value["message"]
            reply_node = "ask_user"
            yield sse({"kind": "interrupt", **snapshot.interrupts[0].value})
        elif not reply and snapshot.values.get("type") == "text":
            # Greeting answered inline by the router (not token-streamed) -> emit it whole.
            reply = str(snapshot.values.get("data") or "")
            reply_node = "router"
            yield sse({"kind": "envelope", "type": "text", "data": reply, "data_type": "string"})

        def enrich(node: str) -> dict:
            meta: dict = {"node": node}
            if model_name := model_by_node.get(node):
                meta["model"] = model_name
            extra: dict = {"meta": meta}
            if usage := usage_by_node.get(node):
                extra["usage"] = usage
            return extra

        # Persist the turn only now: inserting the user row before the run would make
        # JobSearchAgent load the current query as history and duplicate it.
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
        for node, row in tool_rows:
            await Message.create({"thread_id": request.thread_id, "role": "ai", "run_id": run_id, **enrich(node), **row})
        if reply:
            await Message.create(
                {
                    "thread_id": request.thread_id,
                    "role": "ai",
                    "type": "text",
                    "data": {"text": reply},
                    "data_type": "string",
                    "run_id": run_id,
                    **enrich(reply_node),
                }
            )

    return StreamingResponse(generate(), media_type="text/event-stream")

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from fastapi_startkit.inertia import Inertia

from app.agents.chat import ChatAgent
from app.agents.graph_agent import SalesAgent
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
        async for chunk in ChatAgent().stream(request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@api.post("/sales/stream")
async def sales_stream(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    async def generate():
        async for chunk in SalesAgent().stream(request.message, config=config):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@api.get("/sales")
async def sales_page():
    return Inertia.render(
        "chat/sales/Index",
    )

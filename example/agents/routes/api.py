from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from fastapi_startkit.inertia import Inertia

from app.agents.chat import RouterAgent
from app.requests.chat import ChatRequest

api = APIRouter()


@api.get("/")
async def index(request: Request):
    return Inertia.render("chat/Index", {
        "user": {"name": "Alice"},
    })

@api.post("/chat")
async def chat(request: ChatRequest):
    async def generate():
        async for chunk in RouterAgent().stream(request.message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi_startkit.inertia import Inertia

from app.agents.chat import ChatAgent
from app.requests.chat import ChatRequest


async def index(request: Request):
    return Inertia.render("Chat/Index", {})


async def store(body: ChatRequest) -> StreamingResponse:
    agent = ChatAgent()
    return StreamingResponse(agent.stream(body.message), media_type="text/plain")

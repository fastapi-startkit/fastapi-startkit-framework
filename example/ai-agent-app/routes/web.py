from fastapi import Request
from fastapi_startkit.fastapi import Router
from fastapi_startkit.inertia import Inertia
from pydantic import BaseModel

router = Router()


async def index(request: Request):
    return Inertia.render(
        "Dashboard/Index",
        {
            "message": "Welcome to AI Agent App",
        },
    )


async def chat_page(request: Request):
    return Inertia.render("Chat/Index", {})


class ChatRequest(BaseModel):
    message: str


async def chat_send(request: Request, body: ChatRequest):
    from packages.agent import Agent, provider, model

    @provider("anthropic")
    @model("claude-haiku-4-5-20251001")
    class ChatAgent(Agent):
        def messages(self):
            return [{"role": "system", "content": "You are a helpful assistant."}]

    agent = ChatAgent()
    response = agent.prompt(body.message)
    return {"reply": response.content}


router.get("/", index)
router.get("/chat", chat_page)
router.post("/chat", chat_send)

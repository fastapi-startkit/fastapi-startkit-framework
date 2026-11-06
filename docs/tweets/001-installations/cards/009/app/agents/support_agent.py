from pydantic import BaseModel
from fastapi_startkit.ai import Agent, provider


class OrderStatus(BaseModel):
    order_id: int
    status: str


@provider("openai")
class SupportAgent(Agent):
    def instructions(self) -> str:
        return "You answer questions about customer orders."

    def tools(self):
        return [order_status]

    def schema(self):
        return OrderStatus

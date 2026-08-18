from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(...)
    thread_id: str = Field("default")

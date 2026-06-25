from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(...)

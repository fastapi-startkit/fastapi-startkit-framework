from enum import StrEnum
from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class Context(StrEnum):
    INCLUDE_USER_PROFILE = "include_user_profile"
    INCLUDE_LAST_JOB_SEARCH_RESPONSE = "include_last_job_search_response"


class InputState(TypedDict):
    query: str


class OutputState(TypedDict):
    type: Literal["text", "tool_response"]
    data: str | list | dict
    data_type: Literal["string", "json"]


class OverallState(TypedDict):
    query: str
    intent: str
    contexts: list[Context]
    type: Literal["text", "tool_response"]
    data: str | list | dict
    data_type: Literal["string", "json"]
    tool_calls: list[dict]  # the calls behind a tool_response: [{"name": ..., "args": ...}]

class RouterOutput(BaseModel):
    """How to handle the user's query."""

    intent: Literal["job_search", "company_research", "chat"]
    contexts: list[Context] = Field(
        default_factory=list,
        description="Extra context the downstream node needs to answer well.",
    )
    reply: str = Field(
        "",
        description="A short, friendly reply to the user. Fill this ONLY when intent is 'chat' "
        "(greetings, thanks, small talk); leave empty for job_search and company_research.",
    )

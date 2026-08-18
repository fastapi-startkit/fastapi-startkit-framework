from fastapi_startkit.masoniteorm import BelongsTo
from fastapi_startkit.masoniteorm.models import Model


class Message(Model):
    __table__ = "messages"

    thread_id: str
    role: str  # user | ai
    type: str  # text | tool_call | tool_response | web_search
    data: dict
    data_type: str  # string | json
    run_id: str | None
    # Annotated as plain `dict` (not `dict | None`): only the exact annotation selects
    # the ORM's JsonCast; unions fall through to the str cast. Nullable in the DB.
    usage: dict  # token counts: {"input": n, "output": n}
    meta: dict  # per-message extras: latency, model, node
    attachments: dict  # documents sent with the message

    thread = BelongsTo("Thread", local_key="thread_id", foreign_key="id")

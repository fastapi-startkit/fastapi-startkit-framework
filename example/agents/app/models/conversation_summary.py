from fastapi_startkit.masoniteorm import BelongsTo
from fastapi_startkit.masoniteorm.models import Model


class ConversationSummary(Model):
    __table__ = "conversation_summaries"

    thread_id: str
    algorithm: str  # user_queries | sliding_window
    through_id: int  # last messages.id this summary covers
    summary: str

    thread = BelongsTo("Thread", local_key="thread_id", foreign_key="id")

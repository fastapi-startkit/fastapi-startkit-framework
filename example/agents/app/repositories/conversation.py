import asyncio
import json
from abc import ABC, abstractmethod

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.models.conversation_summary import ConversationSummary
from app.models.message import Message

SUMMARY_PROMPT = """Condense this conversation into a short summary the assistant can use
as memory: the user's goals, preferences and any decisions made. Use only what is given.
If a previous summary is provided, fold it in rather than repeating it."""


class Summarizer(ABC):
    @abstractmethod
    async def summarize(self, thread_id: str) -> str | None:
        pass


class SlidingWindowSummarizer(Summarizer):
    """Compacts a thread's history into a rolling summary row.

    Summaries live in `conversation_summaries` — one row per compaction with
    `through_id` marking the last message id covered — so the builder can prepend
    the latest one and load only the rows that came after it.
    """

    algorithm = "sliding_window"

    def __init__(
        self,
        model,
        compaction_interval=10,  # Trigger compaction every 10 new invocations.
        overlap_size=2,  # Include last invocation from the previous window.
    ):
        self.model = model
        self.compaction_interval = compaction_interval
        self.overlap_size = overlap_size

    async def summarize(self, thread_id: str) -> str | None:
        latest = await latest_summary(thread_id)
        through_id = latest.through_id if latest else 0

        fresh = list(
            await Message.where("thread_id", thread_id)
            .where("type", "text")
            .where("id", ">", through_id)
            .order_by("id")
            .get()
        )
        if len(fresh) < self.compaction_interval:
            return None

        overlap: list = []
        if latest and self.overlap_size:
            overlap = list(
                reversed(
                    await Message.where("thread_id", thread_id)
                    .where("type", "text")
                    .where("id", "<=", through_id)
                    .order_by("id", "desc")
                    .limit(self.overlap_size)
                    .get()
                )
            )

        transcript = "\n".join(
            f"{'User' if row.role == 'user' else 'AI'}: {row.data.get('text', '')}" for row in overlap + fresh
        )
        parts = [f"Previous summary:\n{latest.summary}"] if latest else []
        parts.append(f"Conversation:\n{transcript}")

        response = await self.model.ainvoke(
            [SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content="\n\n".join(parts))]
        )
        summary = str(response.text)

        await ConversationSummary.create(
            {
                "thread_id": thread_id,
                "algorithm": self.algorithm,
                "through_id": fresh[-1].id,
                "summary": summary,
            }
        )
        return summary


class UserQuerySummarizer(Summarizer):
    """Non-LLM compaction: folds expired turns' user queries into a summary row.

    A turn starts at each user text row. Once more than `keep_turns` turns have
    accumulated past the last summary, the oldest ones expire: their user queries
    are appended as `- <text>` lines to the previous summary and a new
    `conversation_summaries` row is written, with `through_id` pointing at the
    last message row before the oldest kept turn (so expired AI replies are
    covered too).
    """

    algorithm = "user_queries"

    def __init__(self, keep_turns=15):
        self.keep_turns = keep_turns

    async def summarize(self, thread_id: str) -> str | None:
        latest = await latest_summary(thread_id)
        through_id = latest.through_id if latest else 0

        user_rows = list(
            await Message.where("thread_id", thread_id)
            .where("role", "user")
            .where("type", "text")
            .where("id", ">", through_id)
            .order_by("id")
            .get()
        )
        if len(user_rows) <= self.keep_turns:
            return None

        expired = user_rows[: -self.keep_turns]
        boundary_id = user_rows[-self.keep_turns].id
        last_covered = (
            await Message.where("thread_id", thread_id)
            .where("id", "<", boundary_id)
            .order_by("id", "desc")
            .first()
        )

        lines = "\n".join(f"- {row.data.get('text', '')}" for row in expired)
        summary = f"{latest.summary}\n{lines}" if latest else lines

        await ConversationSummary.create(
            {
                "thread_id": thread_id,
                "algorithm": self.algorithm,
                "through_id": last_covered.id,
                "summary": summary,
            }
        )
        return summary


async def latest_summary(thread_id: str) -> ConversationSummary | None:
    return await ConversationSummary.where("thread_id", thread_id).order_by("id", "desc").first()


class ChatConversationBuilder:
    """Fluent builder for a thread's history as langchain messages.

    Configure synchronously, then `await .get()` — that's when rows load, limits
    apply and the summarizer (if any) is dispatched in the background.
    """

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self._tools: list[str] = []
        self._full_turns: int | None = None
        self._last_job_search = False
        self._summarizer: Summarizer | None = None
        self._summary_task: asyncio.Task | None = None
        self._message_limit: int | None = None
        self._query: str | None = None
        self._files: list[tuple[str, str]] = []

    def with_tool_results(self, tools: list[str]):
        # Only these tools' call/response pairs are replayed into the history
        # (none by default).
        self._tools = tools

        return self

    def only_user_messages(self):
        # Only the user's side of the conversation — every turn is shaped user-only.
        return self.keep_full_turns(0)

    def keep_full_turns(self, n: int):
        # The newest n turns keep the AI side (text and tool rows); older turns
        # contribute only the user's text messages.
        self._full_turns = n

        return self

    def with_last_job_search(self):
        self._last_job_search = True

        return self

    def summarize_if_needed(self, summarizer: Summarizer):
        # dispatches the background task to summarize the conversation
        self._summarizer = summarizer

        return self

    def limit_messages(self, n: int):
        self._message_limit = n

        return self

    def with_query(self, query: str | None):
        # The runner sends the live query itself; the route persists it before the
        # run, so drop that row from history to avoid sending it twice.
        self._query = query

        return self

    def include_content_as_file(self, content: str, name: str = "file"):
        self._files.append((name, content))

        return self

    def include_resume_as_file(self, content: str):
        self.include_content_as_file(content, name="resume")

        return self

    def include_profile_as_file(self, content: str):
        self.include_content_as_file(content, name="profile")

        return self

    async def get(self) -> list[AIMessage | HumanMessage | ToolMessage]:
        messages: list[AIMessage | HumanMessage | ToolMessage] = []

        # turn 10 [user, ai, tools], turn 9 [user, ai], turn 8 [user, ai], ... [Summarizer]

        summary = await latest_summary(self.thread_id)
        if summary:
            messages.append(AIMessage(content=f"Summary of the conversation so far: {summary.summary}"))

        history = self._trim(self._to_messages(await self._rows(summary)))
        messages.extend(history)

        if self._last_job_search and (last := await self._last_job_search_row()):
            messages.append(AIMessage(content=f"Previous job search results: {json.dumps(last.data)}"))

        messages.extend(HumanMessage(content=f"[Document: {name}]\n{content}") for name, content in self._files)

        if self._summarizer is not None:
            # Fire and forget once our own queries are done — the DB connection can't
            # run interleaved operations. Compaction lands for the *next* turn.
            self._summary_task = asyncio.create_task(self._summarizer.summarize(self.thread_id))

        return messages

    async def _rows(self, summary: ConversationSummary | None) -> list[Message]:
        query = self._window(summary)

        if self._full_turns == 0:
            query = query.where("role", "user").where("type", "text")
        elif self._full_turns is not None and (boundary := await self._boundary_id(summary, self._full_turns)):
            # Older turns contribute only the user's text; rows from the boundary on keep
            # everything. Raw because grouped where(lambda) drops the table prefix upstream.
            query = query.where_raw('("role" = ? AND "type" = ? OR "id" >= ?)', ("user", "text", boundary))

        rows = list(await query.order_by("id").get())

        if self._query:
            for i in range(len(rows) - 1, -1, -1):
                if rows[i].role == "user" and rows[i].type == "text" and rows[i].data.get("text") == self._query:
                    del rows[i]
                    break
        return rows

    def _window(self, summary: ConversationSummary | None):
        query = Message.where("thread_id", self.thread_id).where("type", "!=", "summary")
        if summary:
            query = query.where("id", ">", summary.through_id)
        return query

    async def _boundary_id(self, summary: ConversationSummary | None, n: int) -> int | None:
        # Id of the oldest user row that still gets a full turn, or None when the
        # whole window fits. When _query is set, the route has persisted the live
        # query as the newest user row (dropped later) — skip it when counting.
        offset = n - 1 + (1 if self._query else 0)
        row = await (
            self._window(summary)
            .where("role", "user")
            .where("type", "text")
            .order_by("id", "desc")
            .offset(offset)
            .first()
        )
        return row.id if row else None

    def _to_messages(self, rows: list[Message]) -> list[AIMessage | HumanMessage | ToolMessage]:
        messages: list[AIMessage | HumanMessage | ToolMessage] = []
        i = 0
        while i < len(rows):
            row = rows[i]
            if row.type == "text":
                text = row.data.get("text", "")
                messages.append(HumanMessage(content=text) if row.role == "user" else AIMessage(content=text))
            elif row.type == "tool_call":
                # RememberMixin writes the call and its response adjacently; replay
                # them as the paired AIMessage + ToolMessage providers expect.
                response = rows[i + 1] if i + 1 < len(rows) and rows[i + 1].type == "tool_response" else None
                name = row.data.get("name", "")
                if response is not None and name in self._tools:
                    call_id = f"call_{response.id}"
                    messages.append(
                        AIMessage(
                            content="",
                            tool_calls=[{"name": name, "args": row.data.get("args", {}), "id": call_id}],
                        )
                    )
                    messages.append(ToolMessage(content=json.dumps(response.data), tool_call_id=call_id, name=name))
                if response is not None:
                    i += 1  # the response row is consumed with its call either way
            i += 1
        return messages

    def _trim(self, history: list) -> list:
        if self._message_limit is not None:
            history = history[-self._message_limit :]

        # Trimming may have cut an AIMessage(tool_calls) off its ToolMessage; a
        # response without its call breaks providers, so drop the orphan.
        while history and isinstance(history[0], ToolMessage):
            history.pop(0)
        return history

    async def _last_job_search_row(self) -> Message | None:
        return (
            await Message.where("thread_id", self.thread_id)
            .where("role", "ai")
            .where("type", "tool_response")
            .order_by("id", "desc")
            .first()
        )

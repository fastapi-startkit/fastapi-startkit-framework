import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.models.conversation_summary import ConversationSummary
from app.models.message import Message
from app.models.thread import Thread
from app.repositories.conversation import ChatConversationBuilder, SlidingWindowSummarizer, UserQuerySummarizer
from tests.test_case import TestCase


class FakeSummaryModel:
    """Stands in for the summarizer's chat model; records what it was asked."""

    def __init__(self, reply="They discussed remote Python roles."):
        self.reply = reply
        self.calls: list = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.reply)


class ConversationTestCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.thread_id = f"test-{uuid.uuid4()}"
        await Thread.first_or_create({"id": self.thread_id}, {"id": self.thread_id})

    async def asyncTearDown(self):
        await ConversationSummary.where("thread_id", self.thread_id).delete()
        await Message.where("thread_id", self.thread_id).delete()
        await Thread.where("id", self.thread_id).delete()
        await super().asyncTearDown()

    async def seed(self, role: str, type_: str, data: dict | list, data_type: str = "string") -> Message:
        return await Message.create(
            {
                "thread_id": self.thread_id,
                "role": role,
                "type": type_,
                "data": data,
                "data_type": data_type,
                "run_id": None,
            }
        )

    async def seed_turns(self, n: int, start: int = 0) -> None:
        for i in range(start, start + n):
            await self.seed("user", "text", {"text": f"question {i}"})
            await self.seed("ai", "text", {"text": f"answer {i}"})

    def builder(self) -> ChatConversationBuilder:
        return ChatConversationBuilder(self.thread_id)


class TestChatConversationBuilder(ConversationTestCase):
    async def test_maps_text_rows_to_human_and_ai_messages(self):
        await self.seed("user", "text", {"text": "remote only please"})
        await self.seed("ai", "text", {"text": "Got it."})

        messages = await self.builder().get()

        assert [type(m) for m in messages] == [HumanMessage, AIMessage]
        assert [m.content for m in messages] == ["remote only please", "Got it."]

    async def test_only_user_messages_drops_ai_replies(self):
        await self.seed("user", "text", {"text": "remote only please"})
        await self.seed("ai", "text", {"text": "Got it."})

        messages = await self.builder().only_user_messages().get()

        assert [type(m) for m in messages] == [HumanMessage]
        assert [m.content for m in messages] == ["remote only please"]

    async def test_with_query_drops_the_current_turns_persisted_user_row(self):
        await self.seed("user", "text", {"text": "hello"})
        await self.seed("user", "text", {"text": "find python jobs"})

        messages = await self.builder().with_query("find python jobs").get()

        assert [m.content for m in messages] == ["hello"]

    async def test_skips_tool_rows_by_default(self):
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")

        assert await self.builder().get() == []

    async def test_with_tool_results_replays_the_call_response_pair(self):
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        response_row = await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")

        messages = await self.builder().with_tool_results(["job_search_tool"]).get()

        call_message, tool_message = messages
        assert isinstance(call_message, AIMessage) and isinstance(tool_message, ToolMessage)
        call = call_message.tool_calls[0]
        assert call["name"] == "job_search_tool"
        assert call["args"] == {"query": "python"}
        assert tool_message.tool_call_id == call["id"] == f"call_{response_row.id}"
        assert "Python Developer" in tool_message.content

    async def test_with_tool_results_only_includes_the_named_tools(self):
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")

        assert await self.builder().with_tool_results(["company_research_tool"]).get() == []

    async def test_with_last_job_search_appends_the_latest_tool_response(self):
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Old Role"}], "json")
        await self.seed("ai", "tool_response", [{"id": 2, "title": "Python Developer"}], "json")

        messages = await self.builder().with_last_job_search().get()

        assert len(messages) == 1
        assert "Python Developer" in messages[0].content
        assert "Old Role" not in messages[0].content

    async def test_limit_messages_keeps_the_newest(self):
        await self.seed_turns(3)

        messages = await self.builder().limit_messages(2).get()

        assert [m.content for m in messages] == ["question 2", "answer 2"]

    async def test_keep_full_turns_keeps_ai_replies_only_for_the_newest_turns(self):
        await self.seed_turns(3)

        messages = await self.builder().keep_full_turns(2).get()

        assert [m.content for m in messages] == ["question 0", "question 1", "answer 1", "question 2", "answer 2"]
        assert isinstance(messages[0], HumanMessage)

    async def test_keep_full_turns_is_a_noop_when_history_fits(self):
        await self.seed_turns(2)

        messages = await self.builder().keep_full_turns(5).get()

        assert [m.content for m in messages] == ["question 0", "answer 0", "question 1", "answer 1"]

    async def test_keep_full_turns_zero_keeps_only_user_text(self):
        await self.seed_turns(2)
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")

        messages = await self.builder().keep_full_turns(0).get()

        assert [m.content for m in messages] == ["question 0", "question 1"]

    async def test_only_user_messages_drops_tool_replays_too(self):
        await self.seed("user", "text", {"text": "find jobs"})
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")

        messages = await self.builder().with_tool_results(["job_search_tool"]).only_user_messages().get()

        assert [m.content for m in messages] == ["find jobs"]

    async def test_keep_full_turns_drops_tool_rows_in_older_turns(self):
        await self.seed("user", "text", {"text": "find jobs"})
        await self.seed("ai", "tool_call", {"name": "job_search_tool", "args": {"query": "python"}}, "json")
        await self.seed("ai", "tool_response", [{"id": 1, "title": "Python Developer"}], "json")
        await self.seed_turns(1, start=1)

        messages = await self.builder().with_tool_results(["job_search_tool"]).keep_full_turns(1).get()

        assert [m.content for m in messages] == ["find jobs", "question 1", "answer 1"]

    async def test_keep_full_turns_does_not_count_the_live_query_row_as_a_turn(self):
        await self.seed_turns(2)
        await self.seed("user", "text", {"text": "find python jobs"})  # the route persists the live query pre-run

        messages = await self.builder().with_query("find python jobs").keep_full_turns(1).get()

        assert [m.content for m in messages] == ["question 0", "question 1", "answer 1"]

    async def test_files_are_appended_as_labelled_documents(self):
        await self.seed("user", "text", {"text": "hello"})

        messages = await self.builder().include_resume_as_file("10 years of Python").include_profile_as_file("Alice").get()

        assert messages[0].content == "hello"
        assert messages[1].content == "[Document: resume]\n10 years of Python"
        assert messages[2].content == "[Document: profile]\nAlice"


class TestUserQuerySummarizer(ConversationTestCase):
    async def test_does_nothing_until_turns_exceed_the_window(self):
        await self.seed_turns(2)

        summary = await UserQuerySummarizer(keep_turns=2).summarize(self.thread_id)

        assert summary is None
        assert await ConversationSummary.where("thread_id", self.thread_id).first() is None

    async def test_extracts_expired_user_queries_without_a_model(self):
        await self.seed_turns(3)  # turn 0 expires; turns 1-2 stay live

        summary = await UserQuerySummarizer(keep_turns=2).summarize(self.thread_id)

        assert summary == "- question 0"
        row = await ConversationSummary.where("thread_id", self.thread_id).first()
        assert row.algorithm == "user_queries"
        assert row.summary == "- question 0"

    async def test_through_id_covers_the_expired_turn_and_its_reply(self):
        await self.seed_turns(3)

        await UserQuerySummarizer(keep_turns=2).summarize(self.thread_id)

        rows = list(await Message.where("thread_id", self.thread_id).order_by("id").get())
        row = await ConversationSummary.where("thread_id", self.thread_id).first()
        assert row.through_id == rows[1].id  # "answer 0" — the expired turn's reply is covered too

    async def test_folds_new_expired_queries_into_the_previous_summary(self):
        await self.seed_turns(3)
        summarizer = UserQuerySummarizer(keep_turns=2)
        await summarizer.summarize(self.thread_id)
        await self.seed_turns(2, start=3)  # turns 1-2 expire now

        summary = await summarizer.summarize(self.thread_id)

        assert summary == "- question 0\n- question 1\n- question 2"
        latest = await ConversationSummary.where("thread_id", self.thread_id).order_by("id", "desc").first()
        assert latest.summary == "- question 0\n- question 1\n- question 2"

    async def test_builder_prepends_extracted_queries_and_loads_only_live_turns(self):
        await self.seed_turns(3)
        await UserQuerySummarizer(keep_turns=2).summarize(self.thread_id)

        messages = await self.builder().get()

        assert messages[0].content == "Summary of the conversation so far: - question 0"
        assert [m.content for m in messages[1:]] == ["question 1", "answer 1", "question 2", "answer 2"]


class TestSlidingWindowSummarizer(ConversationTestCase):
    async def test_does_nothing_below_the_compaction_interval(self):
        await self.seed_turns(2)
        model = FakeSummaryModel()

        summary = await SlidingWindowSummarizer(model, compaction_interval=10).summarize(self.thread_id)

        assert summary is None
        assert model.calls == []
        assert await ConversationSummary.where("thread_id", self.thread_id).first() is None

    async def test_compacts_and_persists_a_summary_row(self):
        await self.seed_turns(2)  # 4 text rows >= interval
        model = FakeSummaryModel()

        summary = await SlidingWindowSummarizer(model, compaction_interval=4).summarize(self.thread_id)

        assert summary == model.reply
        row = await ConversationSummary.where("thread_id", self.thread_id).first()
        assert row.summary == model.reply
        assert row.algorithm == "sliding_window"
        last_message = await Message.where("thread_id", self.thread_id).order_by("id", "desc").first()
        assert row.through_id == last_message.id
        transcript = model.calls[0][1].content
        assert "question 0" in transcript and "answer 1" in transcript

    async def test_next_window_carries_the_summary_and_the_overlap(self):
        await self.seed_turns(2)
        model = FakeSummaryModel()
        summarizer = SlidingWindowSummarizer(model, compaction_interval=4, overlap_size=2)

        await summarizer.summarize(self.thread_id)
        await self.seed_turns(2, start=2)
        await summarizer.summarize(self.thread_id)

        prompt = model.calls[1][1].content
        assert f"Previous summary:\n{model.reply}" in prompt
        # Overlap: the last two rows of the previous window reappear.
        assert "question 1" in prompt and "answer 1" in prompt
        assert "question 0" not in prompt

    async def test_builder_prepends_the_summary_and_loads_only_newer_rows(self):
        await self.seed_turns(2)
        await SlidingWindowSummarizer(FakeSummaryModel(), compaction_interval=4).summarize(self.thread_id)
        await self.seed("user", "text", {"text": "and in europe?"})

        messages = await self.builder().get()

        assert messages[0].content == "Summary of the conversation so far: They discussed remote Python roles."
        assert [m.content for m in messages[1:]] == ["and in europe?"]

    async def test_summarize_if_needed_dispatches_in_the_background(self):
        await self.seed_turns(2)
        builder = self.builder().summarize_if_needed(SlidingWindowSummarizer(FakeSummaryModel(), compaction_interval=4))

        messages = await builder.get()
        assert builder._summary_task is not None
        await builder._summary_task

        assert len(messages) == 4  # this turn's history is untouched by compaction
        row = await ConversationSummary.where("thread_id", self.thread_id).first()
        assert row is not None

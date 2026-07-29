import json
import uuid

from fastapi_startkit.ai.ai import Ai
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

import app.agents.job_search_graph as graph_module
from app.agents.state import RouterOutput
from app.models.message import Message
from app.models.thread import Thread
from tests.support.fakes import StreamingToolFake, tool_call_message
from tests.test_case import TestCase


class AwaitableSaver:
    def __init__(self, saver):
        self._saver = saver

    def __await__(self):
        async def resolve():
            return self._saver

        return resolve().__await__()


class TestJobsStream(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.thread_id = f"test-{uuid.uuid4()}"

        # Fresh in-memory checkpointer per test: reset the cached compiled graph so
        # job_graph() recompiles against it instead of Postgres.
        from fastapi_startkit.application import app

        app().bind("checkpointer", AwaitableSaver(InMemorySaver()))
        graph_module._graph = None
        self.addCleanup(setattr, graph_module, "_graph", None)
        self.addCleanup(Ai.reset_fakes)

    async def asyncTearDown(self):
        await Message.where("thread_id", self.thread_id).delete()
        await Thread.where("id", self.thread_id).delete()
        await super().asyncTearDown()

    def route_to(self, *decisions: RouterOutput):
        # The router is an agent too now: fake its structured-output turns as JSON
        # content the runner parses back through schema().
        Ai.fake("JobSearchRouterAgent", [AIMessage(content=d.model_dump_json()) for d in decisions])

    async def frames(self, message: str) -> list[dict]:
        response = await self.client.post("/jobs/stream", json={"message": message, "thread_id": self.thread_id})
        frames = []
        for block in response.text.split("\n\n"):
            data = "".join(line[6:] for line in block.split("\n") if line.startswith("data: "))
            if data:
                frames.append(json.loads(data))
        return frames

    async def rows(self) -> list[Message]:
        return list(await Message.where("thread_id", self.thread_id).order_by("id").get())

    def fake_search_calls(self, *messages: AIMessage) -> None:
        Ai._fakes["JobSearchAgent"] = StreamingToolFake(messages=iter(messages))

    async def test_search_streams_the_envelope_and_persists_the_turn(self):
        self.route_to(RouterOutput(intent="job_search"))
        self.fake_search_calls(tool_call_message("python developer"))
        Ai.fake("JobSummarizerAgent", [AIMessage(content="Here is the Python Developer role.")])

        frames = await self.frames("find python jobs")

        envelope = next(f for f in frames if f["kind"] == "envelope")
        assert envelope["node"] == "job_search"
        assert [job["title"] for job in envelope["data"]] == ["Python Developer"]
        assert envelope["tool_calls"] == [{"name": "job_search_tool", "args": {"query": "python developer"}}]
        deltas = "".join(f["text"] for f in frames if f["kind"] == "delta" and f["node"] == "job_summarizer")
        assert deltas == "Here is the Python Developer role."

        rows = await self.rows()
        assert [(m.role, m.type) for m in rows] == [
            ("user", "text"),
            ("ai", "tool_call"),
            ("ai", "tool_response"),
            ("ai", "text"),
        ]
        assert rows[1].data == {"name": "job_search_tool", "args": {"query": "python developer"}}
        assert rows[3].data == {"text": "Here is the Python Developer role."}
        assert rows[3].meta["agent"] == "JobSummarizerAgent"
        assert rows[1].run_id is not None and rows[0].run_id is None

    async def test_greeting_is_answered_inline_by_the_router(self):
        self.route_to(RouterOutput(intent="chat", reply="Hello! How can I help?"))

        frames = await self.frames("hi")

        assert {"kind": "envelope", "type": "text", "data": "Hello! How can I help?", "data_type": "string"} in frames

        rows = await self.rows()
        assert [(m.role, m.type) for m in rows] == [("user", "text"), ("ai", "text")]
        assert rows[1].meta["agent"] == "JobSearchRouterAgent"

    async def test_no_jobs_interrupts_then_a_reply_resumes_the_search(self):
        self.route_to(RouterOutput(intent="job_search"))
        self.fake_search_calls(tool_call_message("cobol mainframe antarctica"), tool_call_message("python developer"))
        Ai.fake("JobSummarizerAgent", [AIMessage(content="Found it after refining.")])

        frames = await self.frames("any cobol roles?")

        interrupt = next(f for f in frames if f["kind"] == "interrupt")
        assert interrupt["reason"] == "no_jobs"
        assert (await self.rows())[-1].meta["agent"] == "ask_user"

        # The next message on this thread resumes the paused graph with a refined query.
        frames = await self.frames("python developer")

        envelope = next(f for f in frames if f["kind"] == "envelope")
        assert [job["title"] for job in envelope["data"]] == ["Python Developer"]
        assert not [f for f in frames if f["kind"] == "interrupt"]
        assert (await self.rows())[-1].data == {"text": "Found it after refining."}

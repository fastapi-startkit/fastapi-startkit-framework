"""The Agent backend runs on LangGraph (create_agent), tested offline.

These exercise the real ``_run``/``_stream`` path — no ``fake()`` short-circuit.
Instead of mutating the agent, we patch the single seam the backend uses to build
a model (``langchain.chat_models.init_chat_model``) with pytest's ``monkeypatch``
and feed it a scripted :func:`fake_chat_model`. The public API is unchanged:
``prompt()`` still returns an AgentResponse and ``stream()`` still yields strings.
"""

import langchain.chat_models as chat_models
import pytest
from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool

from fastapi_startkit.ai import Document, fake_chat_model
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.config import AIConfig
from fastapi_startkit.ai.response import AgentResponse
from fastapi_startkit.application import app


@pytest.fixture(autouse=True)
def ai_config():
    container = app()
    container.bind("ai", AIConfig())
    container.make("config").set("ai", AIConfig())


@pytest.fixture
def scripted_model(monkeypatch):
    """Replace the model the backend builds with a scripted fake, offline."""

    def install(turns):
        model = fake_chat_model(turns)
        monkeypatch.setattr(chat_models, "init_chat_model", lambda *a, **k: model)
        return model

    return install


@tool
def search_jobs(query: str) -> str:
    """Search the job board for roles matching the query."""
    return "Python Developer at Shopify"


class JobAssistant(Agent):
    _instructions = "You help users find jobs."

    def tools(self):
        return [search_jobs]


# ─── prompt() drives the create_agent loop ────────────────────────────────────


def test_prompt_returns_agent_response(scripted_model):
    scripted_model([AIMessage(content="hello back")])

    result = Agent().prompt("hi there")

    assert isinstance(result, AgentResponse)
    assert result.content == "hello back"
    Agent().assert_not_prompted()  # a fresh instance has its own empty log


def test_prompt_runs_a_full_tool_calling_loop(scripted_model):
    scripted_model(
        [
            AIMessage(
                content="",
                tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
            ),
            AIMessage(content="Here is a Python Developer role at Shopify."),
        ]
    )

    result = JobAssistant().prompt("find me a python job")

    assert result.content == "Here is a Python Developer role at Shopify."
    # The loop ran: user → AI(tool_call) → tool result → AI(final).
    assert len(result.raw["messages"]) == 4


def test_prompt_maps_usage_metadata(scripted_model):
    scripted_model([AIMessage(content="done", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})])

    result = Agent().prompt("anything")

    assert result.usage == {"input": 11, "output": 7}


def test_build_model_passes_langchain_provider_key(monkeypatch):
    captured = {}

    def fake_init(model, **kwargs):
        captured["model"] = model
        captured["provider"] = kwargs.get("model_provider")
        return fake_chat_model([AIMessage(content="ok")])

    monkeypatch.setattr(chat_models, "init_chat_model", fake_init)

    class GoogleAgent(Agent):
        _provider = "google"

    GoogleAgent().prompt("hi")

    assert captured["provider"] == "google_genai"
    assert captured["model"] == "gemini-2.0-flash"


# ─── streaming ────────────────────────────────────────────────────────────────


def test_stream_yields_tokens_from_the_model(scripted_model):
    scripted_model([AIMessage(content="streamed reply")])

    chunks = list(Agent().stream("hello"))

    assert "".join(chunks) == "streamed reply"


# ─── model / message building (unit) ──────────────────────────────────────────


def test_resolve_model_falls_back_to_lab_default():
    assert Agent()._resolve_model() == "claude-sonnet-4-6"

    class GoogleAgent(Agent):
        _provider = "google"

    assert GoogleAgent()._resolve_model() == "gemini-2.0-flash"


def test_resolve_model_prefers_explicit_override():
    assert Agent()._resolve_model("my-model") == "my-model"


def test_instructions_come_from_the_attribute_not_messages():
    agent = JobAssistant()

    resolved_system, history = agent._build_messages("find me a job")

    assert resolved_system == "You help users find jobs."
    # messages() is conversation-only; no system entry leaks into history.
    assert all(m.get("role") != "system" for m in history)


def test_instructions_can_be_a_method_override():
    class DynamicAgent(Agent):
        def instructions(self) -> str:
            return "Computed identity."

    resolved_system, _history = DynamicAgent()._build_messages("hi")

    assert resolved_system == "Computed identity."


def test_no_instructions_resolves_to_none():
    resolved_system, _history = Agent()._build_messages("hi")

    assert resolved_system is None


def test_build_messages_inlines_text_attachment():
    doc = Document(content="Q3 revenue was $1.2M.", name="q3-report.txt")

    _system, history = Agent()._build_messages("Summarise this report.", attachments=[doc])

    user_content = history[-1]["content"]
    assert user_content[0] == {"type": "text", "text": "Summarise this report."}
    assert user_content[1]["type"] == "text"
    assert "q3-report.txt" in user_content[1]["text"]


def test_build_messages_encodes_binary_attachment_as_file_block():
    doc = Document(content=b"%PDF-1.7 ...", name="q3.pdf", media_type="application/pdf")

    _system, history = Agent()._build_messages("Summarise", attachments=[doc])

    block = history[-1]["content"][1]
    assert block["type"] == "file"
    assert block["mime_type"] == "application/pdf"
    assert block["base64"] == doc.to_base64()

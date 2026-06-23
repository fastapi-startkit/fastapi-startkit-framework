"""The Agent backend runs on LangGraph (create_agent), tested offline.

These exercise the real ``_run``/``_stream`` path — no fake() short-circuit — by
injecting a scripted fake chat model through the ``_build_model`` seam. The public
API is unchanged; ``prompt()`` still returns an AgentResponse, ``stream()`` still
yields strings.
"""

from langchain_core.messages import AIMessage, ToolCall
from langchain_core.tools import tool

from fastapi_startkit.ai import Document, fake_chat_model
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


def _with_model(agent: Agent, turns) -> Agent:
    """Patch the agent's model seam to replay scripted turns offline."""
    model = fake_chat_model(turns)
    agent._build_model = lambda *a, **k: model  # type: ignore[method-assign]
    return agent


@tool
def search_jobs(query: str) -> str:
    """Search the job board for roles matching the query."""
    return "Python Developer at Shopify"


class JobAssistant(Agent):
    def messages(self):
        return [{"role": "system", "content": "You help users find jobs."}]

    def tools(self):
        return [search_jobs]


# ─── prompt() drives the create_agent loop ────────────────────────────────────


def test_prompt_returns_agent_response_from_langgraph():
    agent = _with_model(Agent(), [AIMessage(content="hello back")])

    result = agent.prompt("hi there")

    assert isinstance(result, AgentResponse)
    assert result.content == "hello back"
    agent.assert_prompted()


def test_prompt_runs_a_full_tool_calling_loop():
    agent = _with_model(
        JobAssistant(),
        [
            AIMessage(
                content="",
                tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
            ),
            AIMessage(content="Here is a Python Developer role at Shopify."),
        ],
    )

    result = agent.prompt("find me a python job")

    assert result.content == "Here is a Python Developer role at Shopify."
    # The loop ran: user → AI(tool_call) → tool result → AI(final).
    assert len(result.raw["messages"]) == 4


def test_prompt_maps_usage_metadata():
    reply = AIMessage(content="done", usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})
    agent = _with_model(Agent(), [reply])

    result = agent.prompt("anything")

    assert result.usage == {"input": 11, "output": 7}


# ─── attachments render as LangChain blocks ───────────────────────────────────


def test_attachments_are_built_as_langchain_blocks():
    agent = Agent()
    doc = Document(content="Q3 revenue was $1.2M.", name="q3-report.txt")

    _system, history = agent._build_messages("Summarise this report.", attachments=[doc])

    user_content = history[-1]["content"]
    assert user_content[0] == {"type": "text", "text": "Summarise this report."}
    assert user_content[1]["type"] == "text"
    assert "q3-report.txt" in user_content[1]["text"]


def test_binary_attachment_becomes_a_file_block():
    agent = Agent()
    doc = Document(content=b"%PDF-1.7 ...", name="q3.pdf", media_type="application/pdf")

    _system, history = agent._build_messages("Summarise", attachments=[doc])

    block = history[-1]["content"][1]
    assert block["type"] == "file"
    assert block["mime_type"] == "application/pdf"
    assert block["base64"] == doc.to_base64()


def test_prompt_with_attachment_returns_reply():
    agent = _with_model(JobAssistant(), [AIMessage(content="Summarised.")])
    doc = Document(content="Q3 revenue was $1.2M.", name="q3-report.txt")

    result = agent.prompt("Summarise this report.", attachments=[doc])

    assert result.content == "Summarised."


# ─── provider mapping + model resolution ──────────────────────────────────────


def test_google_provider_maps_to_langchain_google_genai():
    class GoogleAgent(Agent):
        _provider = "google"

    assert GoogleAgent._LANGCHAIN_PROVIDERS["google"] == "google_genai"


def test_resolve_model_falls_back_to_provider_default():
    assert Agent()._resolve_model() == "claude-sonnet-4-6"

    class OpenAIAgent(Agent):
        _provider = "openai"

    assert OpenAIAgent()._resolve_model() == "gpt-4o"


# ─── stream() pulls tokens from the model ─────────────────────────────────────


def test_stream_yields_tokens_from_the_model():
    agent = _with_model(Agent(), [AIMessage(content="streamed reply")])

    chunks = list(agent.stream("hello"))

    assert "".join(chunks) == "streamed reply"
    agent.assert_prompted(times=1)


# ─── fake_chat_model accepts plain strings ────────────────────────────────────


def test_fake_chat_model_accepts_string_shorthand():
    agent = _with_model(Agent(), ["plain string turn"])

    result = agent.prompt("anything")

    assert result.content == "plain string turn"

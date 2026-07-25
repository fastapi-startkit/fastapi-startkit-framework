"""Tests for the ordered per-turn recording format (task #1251).

A recorded turn is an ORDERED list of message dicts capturing the full
interaction, keyed by the hash of the user input:

    [
      {"type": "human", "content": "suggest me jobs"},
      {"type": "ai", "tool_calls": [...], "uses": {...}, "response_time": 12.0},
      {"type": "tool_response", "content_type": "json", "content": "[...]", "response_time": 5.0},
      {"type": "ai", "content": "Here is a job...", "uses": {...}, "response_time": 8.0},
    ]
"""

from fastapi_startkit.ai import recording
from fastapi_startkit.ai.recording import AIMessage, HumanMessage, ToolCallMessage


class TestMessageSerialization:
    def test_human_message_serializes_to_a_human_entry(self):
        assert HumanMessage("suggest me jobs").to_dict() == {"type": "human", "content": "suggest me jobs"}

    def test_ai_message_with_tool_calls_omits_empty_content(self):
        entry = AIMessage(
            tool_calls=[{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1", "type": "tool_call"}],
            uses={"input_token": 117, "output_token": 22, "cache_token": 0, "total_token": 139},
            response_time=12.0,
        ).to_dict()

        assert entry["type"] == "ai"
        assert "content" not in entry
        assert entry["tool_calls"][0]["name"] == "job_search_tool"
        assert entry["uses"]["input_token"] == 117
        assert entry["response_time"] == 12.0

    def test_ai_message_with_a_final_answer_carries_content(self):
        entry = AIMessage(content="Here is a job.", uses={"output_token": 9}, response_time=8.0).to_dict()

        assert entry["type"] == "ai"
        assert entry["content"] == "Here is a job."
        assert "tool_calls" not in entry

    def test_tool_response_infers_json_content_type(self):
        entry = ToolCallMessage(content='[{"id": 2}]', response_time=5.0).to_dict()

        assert entry == {
            "type": "tool_response",
            "content_type": "json",
            "content": '[{"id": 2}]',
            "response_time": 5.0,
        }

    def test_tool_response_infers_text_content_type(self):
        entry = ToolCallMessage(content="no jobs found", response_time=5.0).to_dict()

        assert entry["content_type"] == "text"


class TestUsesFromUsageMetadata:
    def test_maps_langchain_usage_metadata_to_the_uses_shape(self):
        uses = recording.uses_from_usage_metadata(
            {
                "input_tokens": 117,
                "output_tokens": 22,
                "total_tokens": 139,
                "input_token_details": {"cache_read": 40},
            }
        )
        assert uses == {"input_token": 117, "output_token": 22, "cache_token": 40, "total_token": 139}

    def test_handles_missing_metadata(self):
        assert recording.uses_from_usage_metadata(None) == {
            "input_token": 0,
            "output_token": 0,
            "cache_token": 0,
            "total_token": 0,
        }


class TestReconstructResponse:
    def test_final_ai_answer_wins_over_the_tool_result_for_content(self):
        transcript = [
            HumanMessage("suggest me jobs").to_dict(),
            AIMessage(
                tool_calls=[{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
                uses={"input_token": 117, "output_token": 22},
                response_time=12.0,
            ).to_dict(),
            ToolCallMessage(content='[{"id": 2}]', response_time=5.0).to_dict(),
            AIMessage(content="Here is a job.", uses={"input_token": 5, "output_token": 9}, response_time=8.0).to_dict(),
        ]

        response = recording.to_response(transcript)

        assert response.content == "Here is a job."
        assert [tc["name"] for tc in response.tool_calls] == ["job_search_tool"]
        assert response.usage == {"input": 5, "output": 9}
        assert len(response.tool_events) == 1
        assert response.tool_events[0]["content"] == '[{"id": 2}]'

    def test_falls_back_to_tool_result_when_there_is_no_final_ai_answer(self):
        transcript = [
            HumanMessage("suggest me jobs").to_dict(),
            AIMessage(
                tool_calls=[{"name": "job_search_tool", "args": {"query": "python"}, "id": "c1"}],
                uses={"input_token": 117, "output_token": 22},
                response_time=12.0,
            ).to_dict(),
            ToolCallMessage(content='[{"id": 2}]', response_time=5.0).to_dict(),
        ]

        response = recording.to_response(transcript)

        assert response.content == '[{"id": 2}]'
        assert [tc["name"] for tc in response.tool_calls] == ["job_search_tool"]

    def test_plain_text_turn_reconstructs_content_and_no_tool_calls(self):
        transcript = [
            HumanMessage("hello").to_dict(),
            AIMessage(content="Hi there!", uses={"input_token": 3, "output_token": 2}, response_time=4.0).to_dict(),
        ]

        response = recording.to_response(transcript)

        assert response.content == "Hi there!"
        assert response.tool_calls == []


class TestChunksRoundTrip:
    def test_chunks_are_carried_on_the_ai_message(self):
        entry = AIMessage(content="Hi there!", chunks=["Hi", " there!"], response_time=4.0).to_dict()
        assert entry["chunks"] == ["Hi", " there!"]

    def test_chunks_from_transcript_collects_streamed_chunks(self):
        transcript = [
            HumanMessage("hello").to_dict(),
            AIMessage(content="Hi there!", chunks=["Hi", " there!"], response_time=4.0).to_dict(),
        ]
        assert recording.chunks_from_transcript(transcript) == ["Hi", " there!"]

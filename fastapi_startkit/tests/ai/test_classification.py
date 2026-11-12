import json
from typing import Literal, get_args

import httpx
import pytest
from pydantic import StrictBool

from fastapi_startkit.ai import Ai, AIConfig, Classification, state
from fastapi_startkit.ai.classification import (
    Answer,
    Boolean,
    Choice,
    ClassificationAgent,
    ClassificationError,
    ClassificationResult,
    Decisions,
    Score,
)
from fastapi_startkit.ai.classification.decisions import DECISIONS_URL
from fastapi_startkit.application import app

pytest.importorskip("langchain_core")

INPUT = "Our checkout has been down for an hour and I was charged twice. Fix this NOW."


@pytest.fixture(autouse=True)
def ai_config():
    config = AIConfig()
    config.default = "google"
    config.providers["google"].key = "g-test"
    config.providers["openai"].key = "sk-test"
    app().make("config").set("ai", config)
    yield config
    Ai.reset_fakes()


def support_questions():
    return {
        "urgent": Boolean(
            "Does this request need an immediate response?",
            {"true": "Explicitly time-sensitive", "false": "No urgency expressed"},
        ),
        "department": Choice(
            "Which team should handle this request?",
            {
                "billing": "Payments, invoices, and refunds",
                "technical": "Bugs, outages, and integrations",
                "sales": "Pricing, plans, and upgrades",
            },
        ),
        "frustration": Score("How frustrated is the customer?", ["Calm", "Frustrated", "Very angry"]),
    }


def decisions_body(**overrides):
    answers = {
        "urgent": {"type": "noul", "noul": 0.97, "confidence": 0.97},
        "department": {
            "type": "choice",
            "choice": "technical",
            "probabilities": {"billing": 0.3, "sales": 0.05, "technical": 0.65},
            "confidence": 0.65,
        },
        "frustration": {
            "type": "score",
            "score": 1.72,
            "legend": {"0": "Calm", "1": "Frustrated", "2": "Very angry"},
            "probabilities": {"0": 0.02, "1": 0.24, "2": 0.74},
            "confidence": 0.74,
        },
    }
    answers.update(overrides)
    return {"answers": answers, "usage": {"total_input_tokens": 120, "total_output_tokens": 0, "total_tokens": 120}}


class TestBoolean:
    def test_compiles_to_a_noul_question_with_descriptions(self):
        question = Boolean("Urgent?", {"true": "Time-sensitive", "false": "Not urgent"})

        assert question.decision() == {
            "type": "noul",
            "instructions": "Urgent?",
            "criteria": {"true_description": "Time-sensitive", "false_description": "Not urgent"},
        }
        assert question.annotation() is StrictBool
        assert question.describe() == "Urgent?\nAnswer true or false.\ntrue: Time-sensitive\nfalse: Not urgent"

    def test_works_without_descriptions(self):
        question = Boolean("Urgent?")

        assert question.decision() == {"type": "noul", "instructions": "Urgent?"}
        assert question.from_structured("urgent", False) == Answer(value=False, label="false")

    def test_reads_a_decision_as_a_probability_of_yes(self):
        answer = Boolean("Urgent?").from_decision("urgent", {"type": "noul", "noul": 0.2, "confidence": 0.8})

        assert answer.value is False
        assert answer.confidence == 0.8
        assert answer.probabilities == {True: 0.2, False: 0.8}

    def test_labels_the_answer_with_its_description(self):
        question = Boolean("Urgent?", {"true": "Time-sensitive"})

        assert question.from_structured("urgent", True).label == "Time-sensitive"

    @pytest.mark.parametrize("value", ["yes", 1, None, "true"])
    def test_rejects_a_non_bool_answer(self, value):
        with pytest.raises(ClassificationError, match="'urgent' expects true or false"):
            Boolean("Urgent?").from_structured("urgent", value)

    @pytest.mark.parametrize("noul", [1.5, -0.1, "0.9", None, True])
    def test_rejects_a_noul_outside_zero_to_one(self, noul):
        with pytest.raises(ClassificationError, match="'urgent' expects a number"):
            Boolean("Urgent?").from_decision("urgent", {"type": "noul", "noul": noul})

    def test_rejects_unknown_description_keys(self):
        with pytest.raises(ValueError, match="only 'true' and 'false'"):
            Boolean("Urgent?", {"yes": "Time-sensitive"})

    def test_rejects_empty_instructions(self):
        with pytest.raises(ValueError, match="non-empty instructions"):
            Boolean("  ")


class TestChoice:
    def test_compiles_to_a_choice_question(self):
        question = Choice("Which team?", {"billing": "Payments", "technical": "Bugs"})

        assert question.decision() == {
            "type": "choice",
            "instructions": "Which team?",
            "criteria": {"billing": "Payments", "technical": "Bugs"},
        }
        assert question.annotation() == Literal["billing", "technical"]
        assert (
            question.describe()
            == "Which team?\nAnswer with exactly one of these keys:\nbilling: Payments\ntechnical: Bugs"
        )

    def test_accepts_a_list_of_keys(self):
        question = Choice("Which team?", ["billing", "technical"])

        assert question.decision()["criteria"] == {"billing": "", "technical": ""}
        assert question.from_structured("team", "billing").label == "billing"

    def test_reads_a_decision_with_probabilities(self):
        answer = Choice("Which team?", ["billing", "technical"]).from_decision(
            "team",
            {
                "type": "choice",
                "choice": "technical",
                "probabilities": {"billing": 0.1, "technical": 0.9},
                "confidence": 0.9,
            },
        )

        assert (answer.value, answer.confidence) == ("technical", 0.9)
        assert answer.probabilities == {"billing": 0.1, "technical": 0.9}

    @pytest.mark.parametrize("value", ["marketing", None, 1])
    def test_rejects_an_unknown_choice(self, value):
        with pytest.raises(ClassificationError, match=r"'team' expects one of \['billing', 'technical'\]"):
            Choice("Which team?", ["billing", "technical"]).from_structured("team", value)

    def test_rejects_an_unknown_choice_from_decisions(self):
        with pytest.raises(ClassificationError, match="expects one of"):
            Choice("Which team?", ["billing", "technical"]).from_decision("team", {"type": "choice", "choice": "sales"})

    @pytest.mark.parametrize("options", [["billing"], [], ["", "technical"]])
    def test_rejects_too_few_or_empty_options(self, options):
        with pytest.raises(ValueError, match="Choice"):
            Choice("Which team?", options)


class TestScore:
    def test_compiles_to_a_score_question(self):
        question = Score("How frustrated?", ["Calm", "Frustrated", "Very angry"])

        assert question.decision() == {
            "type": "score",
            "instructions": "How frustrated?",
            "criteria": ["Calm", "Frustrated", "Very angry"],
        }
        assert get_args(question.annotation()) == (0, 1, 2)
        assert "0: Calm\n1: Frustrated\n2: Very angry" in question.describe()

    def test_rounds_the_weighted_score_to_a_level(self):
        question = Score("How frustrated?", ["Calm", "Frustrated", "Very angry"])

        answer = question.from_decision(
            "frustration", {"type": "score", "score": 0.5, "probabilities": {"0": 0.5, "1": 0.5}, "confidence": 0.5}
        )

        assert (answer.value, answer.label) == (1, "Frustrated")
        assert answer.probabilities == {0: 0.5, 1: 0.5}
        assert answer.raw["score"] == 0.5

    def test_reads_a_structured_index(self):
        answer = Score("How frustrated?", ["Calm", "Very angry"]).from_structured("frustration", 1)

        assert answer == Answer(value=1, label="Very angry")

    @pytest.mark.parametrize("value", [3, -1, True, 1.0, "1"])
    def test_rejects_an_index_outside_the_scale(self, value):
        with pytest.raises(ClassificationError, match="expects a level index from 0 to 2"):
            Score("How frustrated?", ["Calm", "Frustrated", "Very angry"]).from_structured("frustration", value)

    def test_rejects_a_decision_score_outside_the_scale(self):
        with pytest.raises(ClassificationError, match="expects a number from 0 to 2"):
            Score("How frustrated?", ["Calm", "Frustrated", "Very angry"]).from_decision(
                "frustration", {"type": "score", "score": 2.5}
            )

    @pytest.mark.parametrize("levels", [["Calm"], "Calm", ["Calm", " "]])
    def test_rejects_invalid_levels(self, levels):
        with pytest.raises(ValueError, match="Score"):
            Score("How frustrated?", levels)


class TestQuestions:
    def test_rejects_an_empty_question_map(self):
        with pytest.raises(ValueError, match="at least one question"):
            Classification.of(INPUT).questions({})

    @pytest.mark.parametrize("key", ["has space", "", "x" * 65, "ü"])
    def test_rejects_keys_the_decisions_api_does_not_accept(self, key):
        with pytest.raises(ValueError, match="must match"):
            Classification.of(INPUT).questions({key: Boolean("Urgent?")})

    def test_rejects_more_than_a_thousand_questions(self):
        with pytest.raises(ValueError, match="at most 1000 questions"):
            Classification.of(INPUT).questions({f"q{index}": Boolean("Urgent?") for index in range(1001)})

    def test_rejects_values_that_are_not_questions(self):
        with pytest.raises(ValueError, match="must be a Boolean, Choice or Score"):
            Classification.of(INPUT).questions({"urgent": "Is it urgent?"})  # type: ignore[dict-item]

    async def test_classify_without_questions_is_rejected(self):
        with pytest.raises(ValueError, match="at least one question"):
            await Classification.of(INPUT).classify()

    async def test_classify_rejects_an_empty_input(self):
        with pytest.raises(ValueError, match="non-empty input"):
            await Classification.of(" ").questions({"urgent": Boolean("Urgent?")}).classify()

    def test_wrong_answer_type_is_rejected(self):
        with pytest.raises(ClassificationError, match="expects a 'noul' answer, got 'choice'"):
            Boolean("Urgent?").from_decision("urgent", {"type": "choice", "choice": "yes"})


class TestGoogleDecisions:
    async def test_sends_the_questions_to_the_decisions_api(self):
        fake = Decisions.fake([decisions_body()])

        await Classification.of(INPUT).questions(support_questions()).classify()

        assert fake.requests == [
            {
                "model": "gemini-decision-1",
                "input": INPUT,
                "questions": {
                    "urgent": {
                        "type": "noul",
                        "instructions": "Does this request need an immediate response?",
                        "criteria": {
                            "true_description": "Explicitly time-sensitive",
                            "false_description": "No urgency expressed",
                        },
                    },
                    "department": {
                        "type": "choice",
                        "instructions": "Which team should handle this request?",
                        "criteria": {
                            "billing": "Payments, invoices, and refunds",
                            "technical": "Bugs, outages, and integrations",
                            "sales": "Pricing, plans, and upgrades",
                        },
                    },
                    "frustration": {
                        "type": "score",
                        "instructions": "How frustrated is the customer?",
                        "criteria": ["Calm", "Frustrated", "Very angry"],
                    },
                },
            }
        ]

    async def test_returns_typed_answers_by_name(self):
        Decisions.fake([decisions_body()])

        result = await Classification.of(INPUT).questions(support_questions()).classify()

        assert isinstance(result, ClassificationResult)
        assert result["urgent"] is True
        assert result.department == "technical"
        assert result["frustration"] == 2
        assert result.to_dict() == {"urgent": True, "department": "technical", "frustration": 2}
        assert dict(result) == result.to_dict()
        assert list(result) == ["urgent", "department", "frustration"]
        assert len(result) == 3
        assert (result.provider, result.model) == ("google", "gemini-decision-1")
        assert result.usage == {"input": 120, "output": 0}
        assert result.state is None

    async def test_unknown_attribute_raises_attribute_error(self):
        Decisions.fake([decisions_body()])

        result = await Classification.of(INPUT).questions(support_questions()).classify()

        with pytest.raises(AttributeError, match="no question 'priority'"):
            result.priority

    async def test_keeps_labels_confidence_and_probabilities(self):
        Decisions.fake([decisions_body()])

        result = await Classification.of(INPUT).questions(support_questions()).classify()

        assert result.answer("urgent").label == "Explicitly time-sensitive"
        assert result.answer("urgent").confidence == 0.97
        assert result.answer("department").label == "Bugs, outages, and integrations"
        assert result.answer("department").probabilities == {"billing": 0.3, "sales": 0.05, "technical": 0.65}
        assert result.answer("frustration").label == "Very angry"
        assert result.answer("frustration").probabilities == {0: 0.02, 1: 0.24, 2: 0.74}
        assert result.answer("frustration").raw["score"] == 1.72

    async def test_overrides_the_decisions_model(self):
        fake = Decisions.fake(lambda payload: decisions_body())

        result = await Classification.of(INPUT).questions(support_questions()).classify(model="gemini-decision-2")

        assert fake.requests[0]["model"] == "gemini-decision-2"
        assert result.model == "gemini-decision-2"

    async def test_falls_back_to_the_default_decisions_model_when_unconfigured(self, ai_config):
        ai_config.providers["google"].models.pop("default_decisions")
        fake = Decisions.fake([decisions_body()])

        await Classification.of(INPUT).questions(support_questions()).classify()

        assert fake.requests[0]["model"] == "gemini-decision-1"

    async def test_missing_answer_raises(self):
        body = decisions_body()
        del body["answers"]["department"]
        Decisions.fake([body])

        with pytest.raises(ClassificationError, match="no answer for question 'department'"):
            await Classification.of(INPUT).questions(support_questions()).classify()

    async def test_unknown_choice_raises(self):
        Decisions.fake([decisions_body(department={"type": "choice", "choice": "legal"})])

        with pytest.raises(ClassificationError, match="'department' expects one of"):
            await Classification.of(INPUT).questions(support_questions()).classify()

    async def test_fake_without_responses_left_raises(self):
        Decisions.fake([])

        with pytest.raises(RuntimeError, match="No fake Decisions response left"):
            await Classification.of(INPUT).questions(support_questions()).classify()

    def test_reset_fakes_removes_the_decisions_fake(self):
        Decisions.fake([])

        Ai.reset_fakes()

        assert Decisions._faked is None


class TestDecisionsTransport:
    async def test_posts_the_payload_with_the_api_key(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers["x-goog-api-key"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"answers": {}})

        payload = {"model": "gemini-decision-1", "input": INPUT, "questions": {"urgent": Boolean("Urgent?").decision()}}
        body = await Decisions("g-test", transport=httpx.MockTransport(handler)).create(payload)

        assert body == {"answers": {}}
        assert seen == {"url": DECISIONS_URL, "key": "g-test", "body": payload}

    async def test_raises_on_a_safety_error(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                400, json={"error": {"code": "safety", "message": "Blocked by safety filters"}}
            )
        )

        with pytest.raises(ClassificationError, match="failed with 400: safety: Blocked by safety filters"):
            await Decisions("g-test", transport=transport).create({"questions": {}})

    async def test_raises_on_a_non_json_error(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable"))

        with pytest.raises(ClassificationError, match="failed with 503: unavailable"):
            await Decisions("g-test", transport=transport).create({"questions": {}})


class TestStructuredOutput:
    async def test_other_providers_classify_through_a_structured_output_agent(self):
        reply = json.dumps({"urgent": True, "department": "billing", "frustration": 1})

        with ClassificationAgent.fake([reply]):
            result = await Classification.of(INPUT).questions(support_questions()).classify(provider="openai")

        assert result.to_dict() == {"urgent": True, "department": "billing", "frustration": 1}
        assert result.answer("frustration").label == "Frustrated"
        assert result.answer("urgent").confidence is None
        assert (result.provider, result.model) == ("openai", "gpt-4o")
        assert state.text(result.state) == reply
        assert result.usage == state.usage(result.state)

    async def test_does_not_call_the_decisions_api(self):
        fake = Decisions.fake([])

        with ClassificationAgent.fake(['{"urgent": false}']):
            await Classification.of(INPUT).questions({"urgent": Boolean("Urgent?")}).classify(provider="anthropic")

        assert fake.requests == []

    async def test_uses_the_model_override(self):
        with ClassificationAgent.fake(['{"urgent": false}']):
            result = (
                await Classification.of(INPUT)
                .questions({"urgent": Boolean("Urgent?")})
                .classify(provider="openai", model="gpt-4.1-mini")
            )

        assert result.model == "gpt-4.1-mini"

    @pytest.mark.parametrize(
        "reply",
        [
            {"urgent": "yes", "department": "billing", "frustration": 1},
            {"urgent": True, "department": "legal", "frustration": 1},
            {"urgent": True, "department": "billing", "frustration": 7},
            {"urgent": True, "department": "billing"},
        ],
    )
    async def test_invalid_model_output_raises(self, reply):
        with ClassificationAgent.fake([json.dumps(reply)]):
            with pytest.raises(ClassificationError, match="invalid classification"):
                await Classification.of(INPUT).questions(support_questions()).classify(provider="openai")

    def test_schema_uses_question_keys_as_aliases(self):
        schema = ClassificationAgent({"first-contact": Boolean("First contact?"), **support_questions()}).schema()

        assert schema is not None
        json_schema = schema.model_json_schema()
        assert list(json_schema["properties"]) == ["first-contact", "urgent", "department", "frustration"]
        assert json_schema["properties"]["department"]["enum"] == ["billing", "technical", "sales"]
        assert json_schema["properties"]["frustration"]["enum"] == [0, 1, 2]
        assert "Bugs, outages, and integrations" in json_schema["properties"]["department"]["description"]
        assert schema.model_validate({"first-contact": True, "urgent": False, "department": "sales", "frustration": 0})

    def test_agent_without_questions_has_no_schema(self):
        assert ClassificationAgent().schema() is None

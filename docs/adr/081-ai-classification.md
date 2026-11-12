# 081. AI classification with Boolean, Choice and Score questions

- Date: 2026-11-12
- Status: Accepted

## Problem

Applications keep asking a model the same kind of question about a piece of text: is this urgent, which team owns it, how angry is the customer. Today each one writes an `Agent` with a hand-made pydantic schema, a prompt that lists the options, and code that checks the answer is one of them. Laravel ships this as `Laravel\Ai\Classification` with `Boolean`, `Choice` and `Score` questions. The `ai` package has no equivalent.

Google also offers a dedicated endpoint for this job, the [Decisions API](https://aistudio.google.com/docs/decisions-api) (`POST https://generativelanguage.googleapis.com/v1beta/decisions`, model `gemini-decision-1`). It takes the shared `input` and a map of questions typed `noul` (yes/no), `choice` or `score`, and answers each with calibrated probabilities and a `confidence` instead of generated text. It bills input tokens only. The user requires Google classification to go through it.

## Alternatives

- **One builder, a provider-specific path.** (chosen) `Classification` compiles the questions once. When the resolved provider is `google`, it sends them to the Decisions API; every other provider gets a structured-output agent. Both paths return the same result.
- **Structured output for every provider, Google included.** One code path, but it ignores the user's requirement and loses Google's calibrated probabilities and cheaper billing.
- **Decisions API only.** Ties classification to one vendor; OpenAI, Anthropic and Bedrock users get nothing.
- **The `google-genai` SDK's `client.decisions.create`.** Needs `google-genai` 3.2 or later and `v1beta` client options, an extra the `ai` extra does not install. The endpoint is one JSON POST, so `httpx` (already installed through LangChain) is enough and easy to fake.
- **A `ClassificationFake` that replaces the whole classifier.** Tests would skip payload building and answer parsing, the parts most likely to break. Faking only the transport (the Decisions HTTP call, or the chat model through the existing `Agent.fake`) keeps them under test.

## Decision

### API

```python
from fastapi_startkit.ai import Classification
from fastapi_startkit.ai.classification import Boolean, Choice, Score

result = await Classification.of(support_request).questions({
    "urgent": Boolean("Does this request need an immediate response?", {
        "true": "Explicitly time-sensitive",
        "false": "No urgency expressed",
    }),
    "department": Choice("Which team should handle this request?", {
        "billing": "Payments, invoices, and refunds",
        "technical": "Bugs, outages, and integrations",
    }),
    "frustration": Score("How frustrated is the customer?", ["Calm", "Frustrated", "Very angry"]),
}).classify()

result["urgent"]          # True
result.department         # "technical"
result["frustration"]     # 2, the level index
result.answer("frustration").label        # "Very angry"
result.answer("urgent").confidence        # 0.97 on Google, None on structured output
```

`classify(provider=None, model=None)` resolves the provider with `Lab.get_provider(provider, ModelType.DECISIONS)`, which reads the root-level `AIConfig.default_decisions` (env `AI_DEFAULT_DECISIONS_PROVIDER`, default `google`). This matches `default_image`, `default_audio`, `default_transcribe` and `default_embeddings`: each feature picks its provider independently of `AI_PROVIDER`, so an app can chat through Anthropic and still classify through the Decisions API. Falling back to `AI_PROVIDER` when the variable is unset was rejected: `env()` returns a lazy field, so one setting cannot default to another, and no other `default_*` setting does that. The default is `google` because the Decisions API is the native classifier. An app without a Google key sets `AI_DEFAULT_DECISIONS_PROVIDER` to its chat provider.

### Questions

| Question | Arguments | Answer value | Decisions API | Structured-output field |
|---|---|---|---|---|
| `Boolean` | instructions, optional `{"true": ..., "false": ...}` | `bool` | `noul` with `true_description`/`false_description` criteria | `StrictBool` |
| `Choice` | instructions, `{key: description}` or a list of keys (2 to 255; each key 1 to 128 characters, at most 512 UTF-8 bytes, no leading or trailing whitespace, no control characters) | the chosen key | `choice`, criteria = the option map | `Literal[*keys]` |
| `Score` | instructions, ordered levels, lowest first (2 to 255) | `int` level index | `score`, criteria = the levels | `Literal[0..n-1]` |

Each answer is an `Answer(value, label, confidence, probabilities, raw)`. `label` is the description of the chosen value (`"true"`/`"false"` when a `Boolean` has none). `raw` is the provider's answer object, which keeps the Decisions API's weighted `score`.

Question keys must match `[A-Za-z0-9_-]{1,64}`, the Decisions API's rule, so the same questions work on every provider. Keys that name a `ClassificationResult` attribute (`model`, `provider`, `usage`, `state`, `answers`, `answer`, `to_dict`, `get`, `keys`, `items`, `values`, and dunders such as `__init__`) are rejected, because `result.<key>` would return the attribute instead of the answer. Choice option keys are checked against the Decisions API's option-key rules on every provider for the same reason. The structured-output schema names its fields `q0`, `q1`, ... and gives each the key as its alias, so keys such as `first-contact` or `model_name` are valid. An empty question map, a non-`Question` value, an empty input, an unknown `Boolean` description key, fewer than two choices or levels, empty levels, an invalid option key and a reserved question key raise `ValueError` when the question or classification is built.

### Google: Decisions API

`Decisions(api_key, timeout).create(payload)` posts the payload with the `x-goog-api-key` header. The payload is `{"model", "input", "questions"}`. The model defaults to the Google provider's `models.default_decisions` (`gemini-decision-1`, new `ModelType.DECISIONS`, whose key `default_decisions` names both the root-level provider setting and the per-provider model). A non-2xx response raises `ClassificationError` with the status and the API's `error.code` and `error.message` (or the raw body when it has no `error` object), which covers the safety-filter 400s. A transport failure (`httpx.HTTPError`, such as a refused connection or a timeout) and a 2xx body that is not a JSON object also raise `ClassificationError`, with the original exception as the cause.

Answers are mapped back as follows:

- `noul` becomes `noul >= 0.5`, with probabilities `{True: noul, False: 1 - noul}`.
- `choice` must be one of the option keys.
- `score` is the probability-weighted level index and must lie within `[0, n - 1]`. The answer is the level with the highest probability (the lower level on a tie), so it agrees with `confidence`; rounding the mean could pick a level the API rated unlikely (`{0: 0.5, 2: 0.5}` averages to 1). Only when `probabilities` is absent is the mean rounded half up. The mean stays in `raw["score"]`. Probability keys may be level indices (`"0"`) or level texts and are turned into indices; any other key, or a probability outside `[0, 1]`, raises `ClassificationError`.

An answer with the wrong `type`, a missing answer, or a value outside these ranges raises `ClassificationError`. Usage becomes `{"input": total_input_tokens, "output": total_output_tokens}`, the same shape `ai.state.usage` returns.

### Other providers: structured output

`ClassificationAgent` is a plain `Agent` whose `schema()` is the pydantic model built from the questions. Each field's description holds the question, its options and their descriptions. `classify` sets the agent's `provider` and `model` and prompts it with the input. It reads `ai.state.structured(...)`, so it uses the same `with_structured_output` path and fakes as every agent. The result carries the turn's `state` and `ai.state.usage(state)`. Invalid output is detected in two places. Real providers run through `with_structured_output(schema, include_raw=True)`, which catches the parse error and returns `parsed=None`; `Runner` keeps the raw `AIMessage` on `state["messages"]` but drops `parsing_error`. When the structured response is missing, `classify` validates the last AI message's tool-call arguments against the schema again, so the `ClassificationError` carries the same pydantic error and names the failing field. JSON in the message content (fakes, cassettes and JSON-mode providers) is validated by `Runner._apply_schema`, whose `ValidationError` is wrapped the same way. With no tool call and no content it raises `ClassificationError("The model returned no classification.")`. A value that passes the schema but fails the question's own check (`Boolean` is not a `bool`, an unknown choice, a score outside the scale) also raises `ClassificationError`. Keeping `parsing_error` in `Runner`'s state was rejected because it would add a key that `create_agent` state does not have.

### Testing

- `Decisions.fake(responses)` takes a list of response bodies or a callable over the payload, and records each payload on `.requests`. `Decisions.reset_fake()` removes it, and `Ai.reset_fakes()` also calls it.
- The structured-output path is faked with the existing `ClassificationAgent.fake([...])`.

## Validation

`fastapi_startkit/tests/ai/test_classification.py`:

- Unit tests for each question's Decisions question, schema annotation and description, and its parsing from Decisions and structured answers, including invalid values.
- `classify()` on `google` through `Decisions.fake`: the exact payload, the default and overridden model, typed values, labels, confidence, probabilities and usage.
- Provider resolution: `AIConfig.default_decisions` defaults to `google` and reads `AI_DEFAULT_DECISIONS_PROVIDER`. `classify()` without a provider follows it and ignores `AI_PROVIDER`, and an explicit `provider` wins.
- `classify()` on `openai` through `ClassificationAgent.fake`: the typed result, the provider and model, `state`, and the schema the agent exposes.
- Error cases: an unknown choice, an out-of-range score, a non-bool, a missing answer and a wrong answer type raise `ClassificationError`; an empty question map, a bad key, a reserved key, invalid option keys and a `Boolean` without descriptions are covered.
- `Score`: the argmax level beats the rounded mean in a bimodal case, ties pick the lower level, the mean is rounded when there are no probabilities, label-keyed probabilities are mapped, and unknown levels raise.
- `parsed=None` from a structured-output model (patched `Runner._build_model`): a rejected tool call names the failing field, rejected JSON content does too, and an empty reply reports no classification.
- `Decisions.create` over an `httpx.MockTransport`: URL, header, body, a 400 safety error, connect and read timeouts, a non-JSON 200, a non-object JSON body, and an error body without an `error` object.
- `uv run pytest tests/ -v` with coverage above the threshold, and `uv run pyrefly check` with no new errors.

# 084. AI stream protocols: Vercel AI SDK, AG-UI and custom protocols

- Date: 2026-11-14
- Status: Accepted

## Problem

`Agent.stream()` yields LangChain `astream_events`-shaped dicts. To serve a chat UI an application has to translate those events into a wire format by hand: open text parts, split reasoning from text, stream tool-call arguments, attach tool results, and terminate the stream. The two common front-ends each expect a fixed protocol:

- Vercel AI SDK UI (`useChat`) reads the [UI message stream](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol): SSE parts (`start`, `start-step`, `text-*`, `reasoning-*`, `tool-input-*`, `tool-output-available`, `finish-step`, `finish`, `error`), the header `x-vercel-ai-ui-message-stream: v1`, and `data: [DONE]`.
- CopilotKit reads [AG-UI](https://docs.ag-ui.com/concepts/events) SSE events (`RUN_STARTED`, `TEXT_MESSAGE_*`, `REASONING_*`, `TOOL_CALL_*`, `RUN_FINISHED`, `RUN_ERROR`) carrying `threadId`/`runId`.

Laravel's AI SDK exposes both on the streamed response: `->stream(...)->usingVercelDataProtocol()`, `->usingAgentUserInteractionProtocol(threadId:, runId:)` and `->usingProtocol(new CustomProtocol)`.

## Alternatives

- **A streamable response object with a normalized event layer.** (chosen) `Agent.stream()` returns `StreamableAgentResponse`, which is still async-iterable (existing `async for` callers keep working) and adds `using_*` methods. One normalizer turns LangChain events into well-bracketed protocol-neutral events; each protocol only maps them to frames.
- **Each protocol reads LangChain events directly.** Every protocol would repeat part bracketing, tool-call id tracking and reasoning extraction, and custom protocols would have to understand LangChain chunk shapes.
- **Standalone helpers (`vercel_stream(agent.stream(...))`).** Works, but does not match the Laravel API being mirrored and gives no home for the invocation and conversation ids.
- **Depend on `ag-ui-protocol` for event models.** Adds a dependency for a handful of JSON shapes.

## Decision

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    return SalesCoach().stream(request.message).using_vercel_data_protocol()


@router.post("/copilot")
async def copilot(request: ChatRequest):
    return SalesCoach().stream(request.message).using_agent_user_interaction_protocol(thread_id="t1")


SalesCoach().stream("...").using_protocol(MyProtocol())
```

- `Agent.stream()` becomes a plain method returning `StreamableAgentResponse(source, conversation_id)`. `invocation_id` is a fresh uuid; `conversation_id` comes from the new `Agent.conversation_id` attribute (default `None`). `AgentFake.stream()` and `AgentRecordFake.stream()` return the same object.
- `StreamableAgentResponse.events()` yields normalized dataclasses from `fastapi_startkit.ai.streaming`: `StreamStarted`, `StepStarted`, `TextStarted`/`TextDelta`/`TextEnded`, `ReasoningStarted`/`ReasoningDelta`/`ReasoningEnded`, `ToolInputStarted`/`ToolInputDelta`/`ToolInputAvailable`, `ToolOutputAvailable`, `StepFinished`, `StreamFinished`, `StreamFailed`.
  - Text comes from string content and `text` blocks; reasoning from `thinking`, `reasoning` and `reasoning_content` blocks and `additional_kwargs["reasoning_content"]`.
  - Only one part is open at a time: switching between text, reasoning and tool input closes the open part, so AG-UI's ordering rules hold.
  - Tool-call chunks are tracked per call in drafts keyed by `index` (then `id`; a chunk with neither continues the last draft), so interleaved calls stream independently. `ToolInputStarted` waits until the call has a name, from a later chunk or the parsed call, and then flushes the buffered arguments, so `toolName`/`toolCallName` are never empty.
  - At `on_chat_model_end` every parsed `tool_calls` entry is matched to a draft by id, then by order. Its `ToolInputAvailable.input` is the parsed arguments, never the streamed text, so arguments that are invalid JSON mid-stream still arrive correct. A call that never streamed is started and its arguments sent as one delta. A draft whose id was generated is aliased to the parsed id. Started drafts with no parsed call (no `on_chat_model_end`) get their decoded streamed arguments when the step closes.
  - Tool results are matched to calls by `ToolMessage.tool_call_id` (through the aliases), falling back to call order only when the result has no id, and are JSON-decoded when possible.
  - A step opens at `on_chat_model_start` and closes before the next step or the finish, so tool results land inside the step that requested them, as in the AI SDK.
  - An `Exception` from the agent is logged, the open text or reasoning part is closed, and it becomes `StreamFailed`; cancellation is not caught.
  - A `StreamableAgentResponse` is single-use: the first `events()` or `async for` runs the agent, and a second consumption raises `RuntimeError` instead of silently running the agent (and its tools) again. Caching events was rejected because it keeps the whole stream in memory and replays stale tool side effects. Sources are wrapped in `contextlib.aclosing`, so a client disconnect closes the agent generator.
- `StreamProtocol` (abstract) has `media_type`, `headers()`, abstract `encode(stream) -> AsyncIterator[str]`, `sse(payload)` and `response(stream) -> StreamingResponse`. `sse` sends a string payload as one `data:` line per line of text, so newlines cannot break SSE framing. `stream.using_protocol(protocol)` returns `protocol.response(stream)`.
- `VercelDataProtocol` maps events to UI message stream parts, adds `x-vercel-ai-ui-message-stream: v1`, and ends with `data: [DONE]`. On failure it emits `{"type": "error", "errorText": ...}` then `[DONE]`. `error_text(exc)` returns `"An error occurred."` because the AI SDK masks errors by default; subclasses override it.
- `AgentUserInteractionProtocol(thread_id=None, run_id=None)` maps events to AG-UI. `threadId` defaults to the conversation id and then the invocation id; `runId` defaults to the invocation id. Reasoning uses the current `REASONING_*` events, not the deprecated `THINKING_*`. Steps map to `STEP_STARTED`/`STEP_FINISHED` with `stepName` `step-<n>`. `TOOL_CALL_START` carries `parentMessageId` when the step already opened a text message, so clients attach the call to that assistant message instead of creating another. Tool results are sent as `TOOL_CALL_RESULT` with string `content`. Failure emits `RUN_ERROR` (message from `error_message(exc)`, masked the same way) and no `RUN_FINISHED`.
- Both protocols send `cache-control: no-cache` and `x-accel-buffering: no`.

## Validation

- Unit tests per protocol assert the exact frame sequence for text, reasoning, tool-call and error streams from a scripted event source.
- Normalizer tests cover LangChain chunk shapes with fake chat models.
- FastAPI `TestClient` tests hit routes returning each protocol and check headers and body.
- A test closes the response body early and asserts the source generator was closed.
- Existing `async for event in agent.stream(...)` tests keep passing; framework coverage stays at or above 80%.

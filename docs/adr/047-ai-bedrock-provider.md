# 047. AWS Bedrock provider for the AI module

Date: 2026-10-29

## Problem

The `ai` module supports Google, OpenAI, Anthropic and ElevenLabs. Applications running on AWS want to call models through Amazon Bedrock with their IAM credentials instead of a vendor API key. The current provider plumbing only forwards a single `api_key` to `init_chat_model`, so it cannot pass a region, IAM keys, a session token or a named profile.

## Alternatives

1. Use the Anthropic SDK's Bedrock client directly. It bypasses LangChain, so agents, tools, structured output, streaming and fakes would need a second code path, and it only covers Anthropic models.
2. Use `langchain-aws` `ChatBedrock` (InvokeModel). It needs per-model request bodies and is the legacy path.
3. Use `langchain-aws` `ChatBedrockConverse` through `init_chat_model(model_provider="bedrock_converse")`. It is the same mechanism every other text provider uses, and the Converse API is model-agnostic.

## Decision

Option 3.

- `BedrockConfig` (driver `bedrock`) reads `AWS_REGION` falling back to `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_PROFILE`, the Bedrock API key `AWS_BEARER_TOKEN_BEDROCK` as `key`, and the text model from `AWS_BEDROCK_MODEL` (default `us.anthropic.claude-sonnet-4-6`, a cross-region inference profile id). It is registered as `providers["bedrock"]` in `AIConfig` and exported from `fastapi_startkit.ai`.
- `Lab.BEDROCK` maps to the LangChain provider key `bedrock_converse`.
- `Lab.get_client_options()` returns provider-specific constructor arguments. For Bedrock it maps `region`, `access_key_id`, `secret_access_key`, `session_token` and `profile` to `region_name`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token` and `credentials_profile_name`, and drops empty values so boto3 falls back to its standard credential chain (env, shared config, instance/role credentials). Other providers return `{}`, so their behaviour is unchanged. `Ai.build` merges these options before `provider_options`, so per-agent options still win.
- The optional `bedrock` extra is `fastapi-startkit[ai]` plus `langchain-aws`. `langchain-aws` depends on `langchain-core` and `boto3` but not on `langchain`, which provides `init_chat_model`. Listing only `langchain-aws` made `pip install fastapi-startkit[bedrock]` fail with `ModuleNotFoundError: langchain`. The self-reference keeps the LangChain pins in one place (the `ai` extra), so `[bedrock]` alone is a working install and `[ai]` alone still excludes `langchain-aws`. Nothing in the framework imports `langchain-aws`; `init_chat_model` imports it only when a Bedrock agent builds its model and raises LangChain's `ImportError` naming `langchain-aws` when it is missing.

## Validation

- Config tests: env mapping, `AWS_DEFAULT_REGION` fallback, empty defaults, model override, registration in `AIConfig`.
- Lab tests: provider key, default model, model URL, client options with and without credentials, `{}` for other providers.
- Agent build test with a mocked `init_chat_model`: a `provider = "bedrock"` agent passes `model_provider="bedrock_converse"`, the model id and the AWS options, and omits unset credentials.
- Packaging: in a fresh venv, install only `fastapi-startkit[bedrock]`, then build a Bedrock agent with mocked AWS env and check that it returns a `ChatBedrockConverse`. Check that `[ai]` alone does not install `langchain-aws`.
- Full suite: `uv run pytest --ignore=tests/masoniteorm/postgres --cov`.

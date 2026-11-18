# 085. MCP router rejects malformed requests and authenticates every verb

Date: 2026-11-18

## Status

Accepted

## Problem

`Server.router()` trusted its input. Malformed JSON, a batch array or a body without `method` raised inside the endpoint and answered 500. A request without an `id` was treated as a notification and dispatched, so an id-less `tools/call` ran the tool and answered 202 with no result. Only `GET` had a route, so `PUT`, `PATCH`, `DELETE` and `OPTIONS` were answered 405 by Starlette before any dependency the app passed to `include_router` ran, which skipped authentication on those verbs.

Apps that exposed MCP to real clients copied the router to fix these cases, so their `/mcp` wiring was no longer `app.include_router(server.router(prefix="/mcp"))`.

## Alternatives

1. Leave the router as is and document the gaps. Every production app keeps its own copy.
2. Add a request guard dependency apps opt into. Two pieces to wire, and the default stays unsafe.
3. Harden `Server.router()` itself. Chosen: the documented one-line mount is safe by default.

## Decision

`Server.router()` answers:

| Request | Response |
|---|---|
| Body is not JSON | 400, `-32700` Parse error |
| Body is not one JSON object (batch, scalar) | 400, `-32600` Invalid request |
| Object is not a JSON-RPC request (no `method`) | 400, `-32600` Invalid request |
| No `id`, method under `notifications/` | 202, empty body, not dispatched |
| No `id`, any other method | 400, `-32600` `The id field is required for <method>.`, not dispatched |
| `GET`, `HEAD`, `PUT`, `PATCH`, `DELETE`, `OPTIONS` | 405, `Allow: POST`, after the app's router dependencies |

`MCPRequest` is a `FormRequest`: `method` is `required().string()`, and its `after` hook requires `id` unless the method starts with `notifications/`. The router runs `MCPRequest.validate_input(body)` and renders a `ValidationException` as `-32600` with `bag.summary()` as the message and `bag.messages` as `data`, as `ValidationExceptionRenderer` does for tool input. `Validated[MCPRequest]` is not used: it fails with the HTTP 422 envelope and FastAPI's own JSON decoding error, not a JSON-RPC error. Only JSON decoding stays a direct check, because it happens before there is input to validate.

Errors use `"id": null`, as JSON-RPC requires when the id cannot be read. `PARSE_ERROR` and `INVALID_REQUEST` join `SERVER_ERROR` in `fastapi_startkit.mcp.exceptions`.

## Consequences

Breaking for clients that sent `tools/list`, `initialize` or other requests without an `id` and relied on the 202; they now get 400 and must send an `id`, as JSON-RPC requires. `Protocol.dispatch` is unchanged.

## Validation

`tests/mcp/test_server.py` covers each row, that an id-less `tools/call` never runs the tool, and that each non-POST verb answers 401 from an app dependency before it answers 405.

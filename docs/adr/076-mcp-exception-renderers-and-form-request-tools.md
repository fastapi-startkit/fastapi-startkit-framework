# 076. MCP exception renderers and FormRequest tools

- Date: 2026-11-09
- Status: Accepted

## Problem

`Protocol.dispatch` caught every exception and answered `{"code": -32000, "message": str(exc)}`. Nothing could change that answer, so a `ValidationException` raised in a tool lost its field errors, and applications wrapped every tool in their own `try/except` to translate exceptions into messages a client could act on.

A tool's input was not validated by the framework. `Tool.schema()` documented the input for `tools/list`, but `tools/call` passed the raw `arguments` dict to `handle`. A tool whose schema is a `FormRequest` had to call `validate_input` itself, so `authorize`, `prepare_for_validation`, the rules and `after` ran only when each tool remembered to.

## Alternatives

- **Catch `ValidationException` in `Protocol.dispatch`.** A second hard-coded branch; the next exception an application wants rendered needs a framework change again.
- **Reuse the application's `exception_manager`.** Its handlers render HTTP responses (the `ValidationException` handler returns a 422 or a redirect), which are not JSON-RPC errors.
- **A container binding for the MCP handler, registered by `McpProvider`.** Works only when the provider is booted, and every `Protocol` resolves global state; tests and servers mounted without the provider would lose validation rendering.
- **An `ExceptionHandler` per server, chosen with a class attribute.** (chosen) It is how `Application` picks its handler class, and registration reuses `register_handler`, `register_render` and the MRO lookup the HTTP side already has.
- **Validate in `Protocol._tools_call`.** Protocol would need to know about tool schemas; the tool owns its schema.

## Decision

`fastapi_startkit.mcp.exceptions` holds:

- `JsonRpcError(code, message, data=None)`, the value a renderer returns.
- `ValidationExceptionRenderer`, which renders a `ValidationException` as `JsonRpcError(-32000, bag.summary(), bag.messages)` and reports nothing.
- `McpExceptionHandler(ExceptionHandler)`, whose `register()` adds that renderer for `ValidationException`.

`Server.exception_handler` is the handler class, `McpExceptionHandler` by default. `Protocol` instantiates it and calls `register()`. When a handler raises, `dispatch` calls `await handler.render(exc, {})`. A `JsonRpcError` result becomes the response's `error`, with `data` included only when it is not `None`. Any other result, including `None` for an exception with no renderer, keeps the previous answer: `-32000` with `str(exc)` and no `data`. Rendering does not report, so unknown exceptions are not logged by the protocol, as before.

An application adds renderers by subclassing:

```python
class AppMcpExceptions(McpExceptionHandler):
    def register(self) -> None:
        super().register()
        self.register_handler(ModelNotFound, ModelNotFoundRenderer())


class AppServer(Server):
    exception_handler = AppMcpExceptions
```

`Tool.call(arguments)` is the entry point `tools/call` uses. When `schema()` returns a `FormRequest` subclass it runs `await schema.validate_input(arguments)` and passes `validated.model_dump()` to `handle`, so `handle` receives coerced values and the result of `prepare_for_validation`. Otherwise it passes `arguments` unchanged. `handle` keeps its signature. A failed validation raises `ValidationException`, which the default handler renders with every field message in `data`. A failed `authorize` raises `AuthorizationException`, which has no MCP renderer and keeps the default answer.

Nested models: a `FormRequest` field typed as a pydantic model with no rules is validated by pydantic, and its errors arrive under dotted keys such as `address.city`. Rules on a nested model are still refused when the class is defined, as before; supporting them needs rule resolution and messages for dotted paths in `Validator`, which is a separate change.

## Validation

`tests/mcp/test_exceptions.py` covers:

- the `ValidationException` rendering with `data`;
- the unchanged default for unknown exceptions;
- a subclass renderer resolved through the MRO, and a `register_render` callable;
- a `FormRequest` tool's failures, its required fields, its coerced and prepared arguments, and nested model errors.

The existing protocol, server and tool tests pass unchanged.

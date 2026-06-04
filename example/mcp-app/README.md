# mcp-app

An example MCP (Model Context Protocol) server built with **fastapi-startkit**'s `Application` class and `FastAPIProvider` — no raw FastAPI wiring required.

## What it demonstrates

| Component | Name | Description |
|---|---|---|
| Tool | `echo` | Returns the caller's message unchanged |
| Tool | `word_count` | Counts words, characters, and lines in text |
| Prompt | `code_review` | Generates a structured code-review prompt |
| Resource | `environment` | Exposes selected env vars as a JSON resource |

## Running

```bash
uv run uvicorn app:app --reload
```

The server listens on `http://127.0.0.1:8000`.

## Quick test

```bash
# Initialize
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | python3 -m json.tool

# List tools
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' | python3 -m json.tool

# Call word_count
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"word_count","arguments":{"text":"Hello world\nHow are you"}},"id":3}' | python3 -m json.tool
```

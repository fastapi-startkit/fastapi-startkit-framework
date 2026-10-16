# mcp-authentication

An MCP server whose tools require an OAuth2 bearer token issued by `fastapi-startkit-auth`. It is the finished app from the [MCP Authentication guide](https://fastapi-startkit.github.io/docs/ai/mcp-authentication), and each step below matches a step there.

## Steps

| Step | Files |
|---|---|
| 1. Install the packages | `pyproject.toml` |
| 2. Configure the environment | `.env.example`, `.env.testing`, `.gitignore`, `config/mcp.py` |
| 3. Configure the OAuth2 server and the guard | `config/auth.py` |
| 4. Create the MCP server and its tools | `app/mcp/tools.py`, `app/mcp/server.py` |
| 5. Protect the MCP endpoint | `app/mcp/auth.py`, `providers/mcp_provider.py`, `bootstrap/application.py`, `artisan` |
| 6. Create a client and issue a token | `app/commands/create_client.py`, `databases/migrations/` |
| 7. Connect a client | — |
| 8. Test it | `pytest.ini`, `tests/test_mcp_authentication.py` |

## Running

```bash
uv sync
cp .env.example .env
uv run python artisan db:migrate
uv run python artisan mcp:client
uv run python artisan serve
```

`mcp:client` prints a client ID and secret. Exchange them for a token:

```bash
curl -s -X POST http://127.0.0.1:8000/oauth/token \
  -d grant_type=client_credentials \
  -d client_id=<client-id> \
  -d client_secret=<client-secret> \
  -d resource=http://127.0.0.1:8000/mcp \
  -d scope="notes:read notes:write"
```

Call a tool with it:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_notes","arguments":{}}}'
```

## Testing

```bash
uv run pytest tests/ -v
```

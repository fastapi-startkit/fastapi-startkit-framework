import json
import os

from fastapi_startkit.mcp import Resource, Response


class EnvResource(Resource):
    """Expose non-sensitive environment variables as a resource."""

    uri = "resource:///env"
    name = "environment"
    description = "A snapshot of selected non-sensitive environment variables."
    mime_type = "application/json"

    # Variables that are safe to expose
    _ALLOWED = {"PATH", "LANG", "TZ", "HOME", "USER", "SHELL", "TERM"}

    async def read(self, **kwargs) -> str:
        safe = {k: v for k, v in os.environ.items() if k in self._ALLOWED}
        return json.dumps(safe, indent=2)

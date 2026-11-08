import time
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from fastapi_startkit.logging import Log


def _model_name(model: BaseChatModel) -> str:
    return getattr(model, "model", None) or getattr(model, "model_name", None) or type(model).__name__


class AgentLogger:
    def handle(self, model: BaseChatModel, handler: Callable) -> Any:
        Log.info(f"request | model={_model_name(model)}")
        started_at = time.monotonic()

        def log_response(final: Any) -> None:
            elapsed = time.monotonic() - started_at
            meta = getattr(final, "usage_metadata", None) or {}
            preview = str(getattr(final, "content", final) or "")[:200].replace("\n", " ")
            Log.info(f"response | {elapsed:.2f}s | in={meta.get('input_tokens', '?')} out={meta.get('output_tokens', '?')} tokens | {preview}")

        return handler(model).then(log_response)

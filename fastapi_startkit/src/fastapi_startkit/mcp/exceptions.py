from dataclasses import dataclass
from typing import Any, override

from fastapi_startkit.exceptions import ValidationException
from fastapi_startkit.exceptions.handler import ExceptionHandler

SERVER_ERROR = -32000


@dataclass(frozen=True)
class JsonRpcError:
    code: int
    message: str
    data: Any = None


class ValidationExceptionRenderer:
    def report(self, exc: ValidationException) -> None:
        pass

    async def render(self, request: Any, exc: ValidationException) -> JsonRpcError:
        return JsonRpcError(SERVER_ERROR, exc.bag.summary(), exc.bag.messages)


class McpExceptionHandler(ExceptionHandler):
    @override
    def register(self) -> None:
        self.register_handler(ValidationException, ValidationExceptionRenderer())

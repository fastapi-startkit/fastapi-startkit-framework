from typing import Any, Dict, Self, Union

from starlette.responses import RedirectResponse

from fastapi_startkit.inertia import session
from fastapi_startkit.inertia.errors import ErrorsInput


class InertiaRedirect(RedirectResponse):
    def with_errors(self, errors: ErrorsInput) -> Self:
        session.with_errors(errors)
        return self

    def with_errors_in(self, bag: str, errors: ErrorsInput) -> Self:
        session.with_errors(errors, bag)
        return self

    def flash(self, key: Union[str, Dict[str, Any]], value: Any = None) -> Self:
        session.flash(key, value)
        return self

    def clear_history(self) -> Self:
        session.clear_history()
        return self

    def preserve_fragment(self) -> Self:
        session.preserve_fragment()
        return self

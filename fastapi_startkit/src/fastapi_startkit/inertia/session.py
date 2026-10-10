import logging
from collections.abc import MutableMapping
from typing import Any, Dict, Union

from starlette.requests import Request

from fastapi_startkit.inertia.context import current_request, current_state
from fastapi_startkit.inertia.errors import ErrorsInput, ValidationErrors

FLASH = "_flash"
ERRORS = "_inertia_errors"
LEGACY_ERRORS = "errors"
PAGE_ERRORS = "_inertia_page_errors"
CLEAR_HISTORY = "_inertia_clear_history"
PRESERVE_FRAGMENT = "_inertia_preserve_fragment"
DEFAULT_BAG = "default"

logger = logging.getLogger("fastapi_startkit.inertia")


def has_session(request: Request) -> bool:
    return "session" in getattr(request, "scope", {})


def store(request: Request) -> MutableMapping[str, Any]:
    if has_session(request):
        return request.session
    state = current_state.get()
    return state.session if state is not None else {}


def put(request: Request, key: str, value: Any) -> None:
    if not has_session(request):
        logger.warning("Inertia queued %r without a session, so it is lost after this request.", key)
    store(request)[key] = value


def pull(request: Request, key: str, default: Any = None) -> Any:
    return store(request).pop(key, default)


def active_request() -> Request:
    request = current_request.get()
    if request is None:
        raise RuntimeError("Inertia session helpers require InertiaMiddleware to be registered.")
    return request


def flash(key: Union[str, Dict[str, Any]], value: Any = None) -> None:
    request = active_request()
    data = {**(store(request).get(FLASH) or {}), **(key if isinstance(key, dict) else {key: value})}
    put(request, FLASH, data)


def with_errors(errors: ErrorsInput, bag: str = DEFAULT_BAG) -> None:
    request = active_request()
    bags = dict(store(request).get(ERRORS) or {})
    bags[bag] = ValidationErrors(bags.get(bag)).merge(ValidationErrors.make(errors)).all()
    put(request, ERRORS, bags)


def clear_history() -> None:
    put(active_request(), CLEAR_HISTORY, True)


def preserve_fragment() -> None:
    put(active_request(), PRESERVE_FRAGMENT, True)


def pull_error_bags(request: Request) -> dict[str, ValidationErrors]:
    bags = {name: ValidationErrors(messages) for name, messages in (pull(request, ERRORS) or {}).items()}
    legacy = pull(request, LEGACY_ERRORS)
    if legacy:
        bags[DEFAULT_BAG] = bags.get(DEFAULT_BAG, ValidationErrors()).merge(legacy)
    return bags


def page_error_bags(request: Request, *, partial: bool) -> dict[str, ValidationErrors]:
    flashed = pull_error_bags(request)
    if flashed:
        store(request)[PAGE_ERRORS] = {name: bag.all() for name, bag in flashed.items()}
    elif not partial:
        pull(request, PAGE_ERRORS)
    return {name: ValidationErrors(messages) for name, messages in (store(request).get(PAGE_ERRORS) or {}).items()}

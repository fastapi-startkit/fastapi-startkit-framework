from typing import Optional

from .exceptions import ViteException


def _resolve_request(context: dict):
    """Return the request from the context, falling back to the request ContextVar."""
    request = context.pop("request", None)
    if request is not None:
        return request

    try:
        from fastapi_startkit.fastapi.context import current_request
    except ImportError:
        return None

    return current_request.get()


def template(name: str, context: Optional[dict] = None):
    """Render a Jinja2 template by name, Laravel ``view()`` style.

    The current request does not need to be passed explicitly: it is taken from
    ``context['request']`` when given, otherwise from the per-request ContextVar
    set by ``RequestContextMiddleware``.
    """
    from fastapi_startkit.application import app as container

    if not container().has("templates"):
        raise ViteException(
            "No 'templates' binding found. Register the ViteProvider (with "
            "`template` enabled) or bind a Jinja2Templates instance as 'templates'."
        )

    templates = container().make("templates")
    context = dict(context or {})
    request = _resolve_request(context)

    try:
        return templates.TemplateResponse(request, name, context)
    except TypeError:
        # Starlette < 0.29 only supports the legacy signature where the request
        # is supplied inside the context dict.
        return templates.TemplateResponse(name, {"request": request, **context})


class Template:
    """Static-style accessor for rendering templates."""

    @staticmethod
    def render(name: str, context: Optional[dict] = None):
        return template(name, context)

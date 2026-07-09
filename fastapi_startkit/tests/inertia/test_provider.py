import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi_startkit.inertia.inertia import Inertia
from fastapi_startkit.inertia.middleware import InertiaMiddleware
from fastapi_startkit.inertia.provider import InertiaProvider


def make_templates():
    """A stand-in for Jinja2Templates exposing an ``env.globals`` dict."""
    return SimpleNamespace(env=SimpleNamespace(globals={}))


class TestRegister:
    def test_binds_inertia(self):
        app = MagicMock()
        InertiaProvider(app).register()
        app.bind.assert_called_once_with("inertia", Inertia)


class TestBoot:
    def test_adds_middleware_and_injects_globals_when_templates_present(self):
        templates = make_templates()
        app = MagicMock()
        app.has.return_value = True
        app.make.side_effect = lambda key: {"templates": templates, "inertia": "INERTIA"}[key]

        InertiaProvider(app).boot()

        app.add_middleware.assert_called_once_with(InertiaMiddleware)
        assert callable(templates.env.globals["inertia"])
        assert templates.env.globals["Inertia"] == "INERTIA"

    def test_skips_globals_when_templates_absent(self):
        app = MagicMock()
        app.has.return_value = False

        InertiaProvider(app).boot()

        app.add_middleware.assert_called_once_with(InertiaMiddleware)
        app.make.assert_not_called()

    def test_inertia_helper_renders_page_markup(self):
        templates = make_templates()
        app = MagicMock()
        app.has.return_value = True
        app.make.side_effect = lambda key: {"templates": templates, "inertia": "INERTIA"}[key]

        InertiaProvider(app).boot()
        helper = templates.env.globals["inertia"]

        page = {"component": "Dashboard", "props": {"count": 3}}
        html = str(helper(page))

        assert json.dumps(page) in html
        assert 'data-page="app"' in html
        assert 'id="app"' in html

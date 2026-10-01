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

    def test_inertia_helper_renders_ssr_body(self):
        templates = make_templates()
        app = MagicMock()
        app.has.return_value = True
        app.make.side_effect = lambda key: {"templates": templates, "inertia": "INERTIA"}[key]

        InertiaProvider(app).boot()
        helper = templates.env.globals["inertia"]

        html = str(helper({"component": "Dashboard", "props": {}, "ssr": {"body": "<main>SSR</main>"}}))

        assert '<div id="app"><main>SSR</main></div>' in html

    def test_inertia_head_renders_ssr_head_entries(self):
        templates = make_templates()
        app = MagicMock()
        app.has.return_value = True
        app.make.side_effect = lambda key: {"templates": templates, "inertia": "INERTIA"}[key]

        InertiaProvider(app).boot()
        helper = templates.env.globals["inertia_head"]

        head = helper({"ssr": {"head": ["<title>Dashboard</title>", '<meta name="description" content="Home">']}})

        assert str(head) == '<title>Dashboard</title><meta name="description" content="Home">'

    def test_inertia_helper_omits_ssr_data_from_client_page_json(self):
        templates = make_templates()
        app = MagicMock()
        app.has.return_value = True
        app.make.side_effect = lambda key: {"templates": templates, "inertia": "INERTIA"}[key]

        InertiaProvider(app).boot()
        helper = templates.env.globals["inertia"]

        page = {
            "component": "Dashboard",
            "props": {"count": 3},
            "ssr": {"head": ["<title>Dashboard</title>"], "body": "<main>SSR</main>"},
        }
        html = str(helper(page))
        client_json = html.split(">", 1)[1].split("</script>", 1)[0]

        assert json.loads(client_json) == {"component": "Dashboard", "props": {"count": 3}}

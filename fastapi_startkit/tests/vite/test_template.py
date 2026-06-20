import pytest
from starlette.requests import Request
from starlette.responses import Response

from fastapi_startkit.application import Application
from fastapi_startkit.providers import Provider
from fastapi_startkit.vite import Template, ViteProvider, template
from fastapi_startkit.vite.exceptions import ViteException


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
        }
    )


def make_app(tmp_path, providers=None, write_template=False) -> Application:
    if write_template:
        templates_dir = tmp_path / "resources" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "index.html").write_text("<h1>{{ title }}</h1>")

    return Application(
        base_path=tmp_path,
        env="testing",
        providers=providers or [ViteProvider],
    )


class _SentinelTemplatesProvider(Provider):
    provider_key = "sentinel_templates"

    def register(self) -> None:
        self.app.bind("templates", "SENTINEL")


class TestTemplateBinding:
    def test_binds_templates_when_enabled_and_none_prebound(self, tmp_path):
        app = make_app(tmp_path)
        assert app.has("templates")

    def test_respects_existing_templates_binding(self, tmp_path):
        app = make_app(tmp_path, providers=[_SentinelTemplatesProvider, ViteProvider])
        assert app.make("templates") == "SENTINEL"

    def test_skips_binding_when_template_disabled(self, tmp_path):
        app = make_app(tmp_path, providers=[(ViteProvider, {"template": False})])
        assert not app.has("templates")

    def test_vite_globals_injected_after_boot(self, tmp_path):
        app = make_app(tmp_path)
        env_globals = app.make("templates").env.globals
        assert "vite" in env_globals
        assert "vite_asset" in env_globals
        assert "vite_react_refresh" in env_globals


class TestTemplateRendering:
    def test_template_helper_returns_template_response(self, tmp_path):
        make_app(tmp_path, write_template=True)
        response = template("index.html", {"request": make_request(), "title": "Hi"})
        assert isinstance(response, Response)

    def test_template_class_render_uses_request_contextvar(self, tmp_path):
        make_app(tmp_path, write_template=True)
        from fastapi_startkit.fastapi.context import current_request

        token = current_request.set(make_request())
        try:
            response = Template.render("index.html", {"title": "Hi"})
        finally:
            current_request.reset(token)

        assert isinstance(response, Response)

    def test_template_raises_when_no_binding(self, tmp_path):
        make_app(tmp_path, providers=[(ViteProvider, {"template": False})])
        with pytest.raises(ViteException):
            template("index.html", {"request": make_request()})

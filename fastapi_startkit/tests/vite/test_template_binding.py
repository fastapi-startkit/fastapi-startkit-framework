import sys
from unittest import mock

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.support import Provider
from fastapi_startkit.vite import ViteProvider
from fastapi_startkit.vite.config.vite import ViteConfig


def make_app(tmp_path, providers=None) -> Application:
    if providers is None:
        providers = [ViteProvider]
    return Application(base_path=tmp_path, env="testing", providers=providers)


class _SentinelTemplatesProvider(Provider):
    provider_key = "sentinel_templates"

    def register(self) -> None:
        self.app.bind("templates", "SENTINEL")


class TestTemplateBinding:
    def test_binds_templates_when_enabled_and_none_prebound(self, tmp_path):
        from starlette.templating import Jinja2Templates

        app = make_app(tmp_path)

        assert app.has("templates")
        assert isinstance(app.make("templates"), Jinja2Templates)

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


class TestMissingJinja2:
    def test_missing_jinja2_raises_clear_install_error(self, tmp_path):
        app = make_app(tmp_path, providers=[])
        provider = ViteProvider(app)

        # Jinja2Templates is only importable from starlette.templating when
        # jinja2 is installed; setting the module to None makes the import fail.
        with mock.patch.dict(sys.modules, {"starlette.templating": None}):
            with pytest.raises(ImportError) as exc_info:
                provider.register_templates(ViteConfig())

        assert "fastapi-startkit[vite]" in str(exc_info.value)

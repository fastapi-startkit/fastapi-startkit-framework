import json

import pytest

from fastapi_startkit.vite.exceptions import ViteException, ViteManifestNotFoundException
from fastapi_startkit.vite.vite import Vite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_vite(tmp_path, build_dir="build", manifest=None, hot_content=None, asset_url=""):
    """Create a Vite instance with an optional manifest.json and/or hot file."""
    public = tmp_path / "public"
    public.mkdir()

    if manifest is not None:
        build = public / build_dir
        build.mkdir(parents=True)
        (build / "manifest.json").write_text(json.dumps(manifest))

    if hot_content is not None:
        (public / "hot").write_text(hot_content)

    # Clear class-level manifest cache between tests
    Vite._manifests.clear()

    return Vite(public_path=str(public), build_directory=build_dir, asset_url=asset_url)


SIMPLE_MANIFEST = {
    "resources/js/app.js": {
        "file": "assets/app-abc123.js",
        "src": "resources/js/app.js",
        "isEntry": True,
    }
}

MANIFEST_WITH_CSS = {
    "resources/js/app.js": {
        "file": "assets/app-abc123.js",
        "src": "resources/js/app.js",
        "isEntry": True,
        "css": ["assets/app-def456.css"],
    }
}


# ---------------------------------------------------------------------------
# Production mode (no hot file)
# ---------------------------------------------------------------------------


class TestProductionMode:
    def test_is_not_running_hot_without_hot_file(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite.is_running_hot() is False

    def test_asset_url_contains_hashed_filename(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        result = vite("resources/js/app.js")
        assert "app-abc123.js" in result

    def test_script_tag_generated(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        result = vite("resources/js/app.js")
        assert "<script" in result
        assert 'type="module"' in result

    def test_css_link_tag_generated(self, tmp_path):
        vite = make_vite(tmp_path, manifest=MANIFEST_WITH_CSS)
        result = vite("resources/js/app.js")
        assert "<link" in result
        assert "app-def456.css" in result

    def test_asset_method_returns_hashed_url(self, tmp_path):
        manifest = {
            "resources/images/logo.png": {
                "file": "assets/logo-xyz789.png",
                "src": "resources/images/logo.png",
            }
        }
        vite = make_vite(tmp_path, manifest=manifest)
        url = vite.asset("resources/images/logo.png")
        assert "logo-xyz789.png" in url

    def test_asset_url_prefix_applied(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST, asset_url="https://cdn.example.com")
        result = vite("resources/js/app.js")
        assert "cdn.example.com" in result

    def test_multiple_entry_points(self, tmp_path):
        manifest = {
            "resources/js/app.js": {
                "file": "assets/app-abc.js",
                "src": "resources/js/app.js",
                "isEntry": True,
            },
            "resources/js/admin.js": {
                "file": "assets/admin-def.js",
                "src": "resources/js/admin.js",
                "isEntry": True,
            },
        }
        vite = make_vite(tmp_path, manifest=manifest)
        result = vite(["resources/js/app.js", "resources/js/admin.js"])
        assert "app-abc.js" in result
        assert "admin-def.js" in result


# ---------------------------------------------------------------------------
# Dev mode (HMR / hot file present)
# ---------------------------------------------------------------------------


class TestDevMode:
    def test_is_running_hot_with_hot_file(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        assert vite.is_running_hot() is True

    def test_dev_url_contains_localhost(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        result = vite("resources/js/app.js")
        assert "localhost:5173" in result

    def test_dev_url_contains_vite_client(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        result = vite("resources/js/app.js")
        assert "@vite/client" in result

    def test_dev_url_entrypoint_included(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        result = vite("resources/js/app.js")
        assert "resources/js/app.js" in result

    def test_custom_hot_origin_used(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:3000")
        result = vite("resources/js/app.js")
        assert "localhost:3000" in result

    def test_asset_in_hot_mode_uses_dev_server(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        url = vite.asset("resources/images/logo.png")
        assert "localhost:5173" in url

    def test_react_refresh_returned_in_dev_mode(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        result = vite.react_refresh()
        assert "@react-refresh" in result
        assert "<script" in result

    def test_react_refresh_empty_in_production(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite.react_refresh() == ""


# ---------------------------------------------------------------------------
# Missing manifest — error with helpful message
# ---------------------------------------------------------------------------


class TestMissingManifest:
    def test_missing_manifest_raises_exception(self, tmp_path):
        vite = make_vite(tmp_path)  # no manifest written
        with pytest.raises(ViteManifestNotFoundException) as exc_info:
            vite("resources/js/app.js")
        assert "manifest" in str(exc_info.value).lower()

    def test_missing_manifest_message_contains_path(self, tmp_path):
        vite = make_vite(tmp_path)
        with pytest.raises(ViteManifestNotFoundException) as exc_info:
            vite("resources/js/app.js")
        assert "manifest.json" in str(exc_info.value)

    def test_unknown_entrypoint_raises_vite_exception(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        with pytest.raises(ViteException):
            vite("resources/js/nonexistent.js")

    def test_manifest_hash_returns_none_when_missing(self, tmp_path):
        vite = make_vite(tmp_path)
        assert vite.manifest_hash() is None


# ---------------------------------------------------------------------------
# manifest_hash
# ---------------------------------------------------------------------------


class TestManifestHash:
    def test_manifest_hash_returns_string_in_production(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        h = vite.manifest_hash()
        assert h is not None
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex

    def test_manifest_hash_is_none_in_hot_mode(self, tmp_path):
        vite = make_vite(tmp_path, hot_content="http://localhost:5173")
        assert vite.manifest_hash() is None

    def test_manifest_hash_changes_when_manifest_changes(self, tmp_path):
        vite1 = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        h1 = vite1.manifest_hash()

        Vite._manifests.clear()

        manifest2 = {
            "resources/js/app.js": {
                "file": "assets/app-different.js",
                "src": "resources/js/app.js",
                "isEntry": True,
            }
        }
        public = tmp_path / "public"
        (public / "build" / "manifest.json").write_text(json.dumps(manifest2))

        vite2 = Vite(public_path=str(public), build_directory="build")
        h2 = vite2.manifest_hash()

        assert h1 != h2


# ---------------------------------------------------------------------------
# ViteProvider — registers Vite service in the container
# ---------------------------------------------------------------------------


class TestViteProvider:
    def test_vite_provider_binds_vite_to_container(self, tmp_path):
        from fastapi_startkit.application import Application
        from fastapi_startkit.vite.providers.provider import ViteProvider

        app = Application(base_path=tmp_path, env="testing", providers=[
            ViteProvider
        ])

        assert app.has("vite")
        vite = app.make("vite")
        assert isinstance(vite, Vite)


# ---------------------------------------------------------------------------
# Configuration: is_css_path helper
# ---------------------------------------------------------------------------


class TestIsCssPath:
    def test_css_extension_is_css(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite._is_css_path("style.css") is True

    def test_scss_extension_is_css(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite._is_css_path("style.scss") is True

    def test_js_extension_is_not_css(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite._is_css_path("app.js") is False

    def test_ts_extension_is_not_css(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        assert vite._is_css_path("app.ts") is False


# ---------------------------------------------------------------------------
# CSP Nonce
# ---------------------------------------------------------------------------


class TestCspNonce:
    def test_use_csp_nonce_generates_random_nonce(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        nonce = vite.use_csp_nonce()
        assert isinstance(nonce, str)
        assert len(nonce) == 40  # secrets.token_hex(20)

    def test_use_csp_nonce_accepts_explicit_value(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        vite.use_csp_nonce("my-nonce-value")
        assert vite.csp_nonce() == "my-nonce-value"

    def test_nonce_included_in_script_tag(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        vite.use_csp_nonce("testnonce")
        result = vite("resources/js/app.js")
        assert "testnonce" in result


# ---------------------------------------------------------------------------
# Flush and preloaded_assets
# ---------------------------------------------------------------------------


class TestFlush:
    def test_flush_clears_preloaded_assets(self, tmp_path):
        vite = make_vite(tmp_path, manifest=SIMPLE_MANIFEST)
        vite("resources/js/app.js")
        vite.flush()
        assert vite.preloaded_assets() == {}

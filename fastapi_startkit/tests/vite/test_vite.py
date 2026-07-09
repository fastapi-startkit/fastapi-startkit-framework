import hashlib
import json
import os

import pytest

from fastapi_startkit.vite.exceptions import ViteException, ViteManifestNotFoundException
from fastapi_startkit.vite.vite import Vite


MANIFEST = {
    "resources/js/app.js": {
        "file": "assets/app-abc123.js",
        "src": "resources/js/app.js",
        "isEntry": True,
        "imports": ["_vendor-xyz.js"],
        "css": ["assets/app-def456.css"],
    },
    "_vendor-xyz.js": {
        "file": "assets/vendor-xyz.js",
        "css": ["assets/vendor-css.css"],
    },
    "resources/images/logo.png": {
        "file": "assets/logo-hash.png",
        "src": "resources/images/logo.png",
    },
}


@pytest.fixture(autouse=True)
def _clear_manifest_cache():
    """The manifest cache is a class attribute shared across instances."""
    Vite._manifests.clear()
    yield
    Vite._manifests.clear()


@pytest.fixture
def public_path(tmp_path):
    return str(tmp_path)


def write_manifest(public_path, build_directory="build", manifest=None):
    build_dir = os.path.join(public_path, build_directory)
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.join(build_dir, "manifest.json")
    with open(path, "w") as f:
        json.dump(manifest if manifest is not None else MANIFEST, f)
    return path


def write_hot_file(public_path, contents="http://localhost:5173"):
    path = os.path.join(public_path, "hot")
    with open(path, "w") as f:
        f.write(contents)
    return path


class TestConfiguration:
    def test_defaults(self, public_path):
        vite = Vite(public_path)
        assert vite.csp_nonce() is None
        assert vite.preloaded_assets() == {}
        assert not vite.is_running_hot()

    def test_use_csp_nonce_generates_and_sets(self, public_path):
        vite = Vite(public_path)
        nonce = vite.use_csp_nonce()
        assert isinstance(nonce, str) and len(nonce) > 0
        assert vite.csp_nonce() == nonce

        assert vite.use_csp_nonce("fixed") == "fixed"
        assert vite.csp_nonce() == "fixed"

    def test_fluent_setters_return_self(self, public_path):
        vite = Vite(public_path)
        assert vite.use_integrity_key("sri") is vite
        assert vite.with_entry_points(["a.js"]) is vite
        assert vite.create_asset_paths_using(lambda p: p) is vite
        assert vite.use_script_tag_attributes({"defer": True}) is vite
        assert vite.use_style_tag_attributes({"media": "all"}) is vite
        assert vite.use_preload_tag_attributes({"x": "y"}) is vite


class TestAssetPath:
    def test_default_asset_path(self, public_path):
        vite = Vite(public_path)
        assert vite._asset_path("build/app.js") == "/build/app.js"

    def test_asset_url_prefix(self, public_path):
        vite = Vite(public_path, asset_url="https://cdn.example.com/")
        assert vite._asset_path("build/app.js") == "https://cdn.example.com/build/app.js"

    def test_custom_resolver(self, public_path):
        vite = Vite(public_path).create_asset_paths_using(lambda p: f"resolved::{p}")
        assert vite._asset_path("build/app.js") == "resolved::build/app.js"


class TestHotMode:
    def test_is_running_hot(self, public_path):
        vite = Vite(public_path)
        assert not vite.is_running_hot()
        write_hot_file(public_path)
        assert vite.is_running_hot()

    def test_call_in_hot_mode(self, public_path):
        write_hot_file(public_path, "http://localhost:5173/")
        vite = Vite(public_path)
        html = vite("resources/js/app.js")
        assert "http://localhost:5173/@vite/client" in html
        assert "http://localhost:5173/resources/js/app.js" in html

    def test_read_hot_origin_falls_back_when_empty(self, public_path):
        write_hot_file(public_path, "   ")
        vite = Vite(public_path)
        assert vite._read_hot_origin() == "http://localhost:5173"

    def test_asset_in_hot_mode(self, public_path):
        write_hot_file(public_path, "http://localhost:5173")
        vite = Vite(public_path)
        assert vite.asset("resources/images/logo.png") == "http://localhost:5173/resources/images/logo.png"

    def test_react_refresh_hot(self, public_path):
        write_hot_file(public_path, "http://localhost:5173")
        vite = Vite(public_path)
        vite.use_csp_nonce("abc")
        html = vite.react_refresh()
        assert "@react-refresh" in html
        assert 'nonce="abc"' in html

    def test_react_refresh_not_hot_returns_empty(self, public_path):
        vite = Vite(public_path)
        assert vite.react_refresh() == ""

    def test_manifest_hash_none_when_hot(self, public_path):
        write_hot_file(public_path)
        vite = Vite(public_path)
        assert vite.manifest_hash() is None


class TestProductionMode:
    def test_call_produces_tags(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        html = vite("resources/js/app.js")

        assert "/build/assets/app-abc123.js" in html
        assert "/build/assets/vendor-xyz.js" in html
        assert "/build/assets/app-def456.css" in html
        assert "rel=\"modulepreload\"" in html
        assert "<script" in html
        assert "<link" in html

    def test_call_accepts_list_of_entrypoints(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        html = vite(["resources/js/app.js"])
        assert "/build/assets/app-abc123.js" in html

    def test_call_populates_preloaded_assets(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite("resources/js/app.js")
        assert vite.preloaded_assets() != {}

    def test_flush_resets_preloaded_assets(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite("resources/js/app.js")
        vite.flush()
        assert vite.preloaded_assets() == {}

    def test_to_html_uses_entry_points(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path).with_entry_points(["resources/js/app.js"])
        assert "/build/assets/app-abc123.js" in vite.to_html()

    def test_asset_returns_public_url(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        assert vite.asset("resources/images/logo.png") == "/build/assets/logo-hash.png"

    def test_custom_build_directory(self, public_path):
        write_manifest(public_path, build_directory="dist")
        vite = Vite(public_path)
        html = vite("resources/js/app.js", build_directory="dist")
        assert "/dist/assets/app-abc123.js" in html

    def test_manifest_hash_returns_md5(self, public_path):
        path = write_manifest(public_path)
        vite = Vite(public_path)
        with open(path, "rb") as f:
            expected = hashlib.md5(f.read()).hexdigest()
        assert vite.manifest_hash() == expected

    def test_manifest_hash_none_when_missing(self, public_path):
        vite = Vite(public_path)
        assert vite.manifest_hash() is None

    def test_manifest_is_cached(self, public_path):
        path = write_manifest(public_path)
        vite = Vite(public_path)
        vite("resources/js/app.js")
        # Removing the file should not matter — it is cached at the class level.
        os.remove(path)
        html = vite("resources/js/app.js")
        assert "/build/assets/app-abc123.js" in html


class TestAttributeResolvers:
    def test_script_tag_attribute_resolver(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite.use_script_tag_attributes(lambda *a: {"data-turbo-track": "reload"})
        html = vite("resources/js/app.js")
        assert 'data-turbo-track="reload"' in html

    def test_style_tag_attribute_resolver_callable(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite.use_style_tag_attributes(lambda *a: {"media": "screen"})
        html = vite("resources/js/app.js")
        assert 'media="screen"' in html

    def test_preload_resolver_returning_false_skips_preloads(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite.use_preload_tag_attributes(lambda *a: False)
        html = vite("resources/js/app.js")
        assert "modulepreload" not in html

    def test_preload_resolver_returning_dict_merges_attributes(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite.use_preload_tag_attributes(lambda *a: {"data-preload": "1"})
        html = vite("resources/js/app.js")
        assert 'data-preload="1"' in html

    def test_nonce_applied_to_tags(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        vite.use_csp_nonce("secret")
        html = vite("resources/js/app.js")
        assert 'nonce="secret"' in html


class TestErrors:
    def test_manifest_not_found_raises(self, public_path):
        vite = Vite(public_path)
        with pytest.raises(ViteManifestNotFoundException):
            vite("resources/js/app.js")

    def test_unknown_entrypoint_raises(self, public_path):
        write_manifest(public_path)
        vite = Vite(public_path)
        with pytest.raises(ViteException):
            vite("resources/js/missing.js")


class TestInternalHelpers:
    def test_find_chunk_by_file_matches(self, public_path):
        vite = Vite(public_path)
        chunk = vite._find_chunk_by_file(MANIFEST, "assets/vendor-xyz.js")
        assert chunk.get("file") == "assets/vendor-xyz.js"

    def test_find_chunk_by_file_returns_stub(self, public_path):
        vite = Vite(public_path)
        chunk = vite._find_chunk_by_file(MANIFEST, "assets/unknown.css")
        assert chunk == {"file": "assets/unknown.css"}

    def test_resolve_imports_handles_cycles(self, public_path):
        vite = Vite(public_path)
        manifest = {
            "a.js": {"file": "a.js", "imports": ["b.js"]},
            "b.js": {"file": "b.js", "imports": ["a.js"]},
        }
        imports = vite._resolve_imports(manifest, manifest["a.js"])
        assert imports == ["b.js", "a.js"]

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("app.css", True),
            ("app.scss", True),
            ("app.less?v=1", True),
            ("app.js", False),
            ("logo.png", False),
        ],
    )
    def test_is_css_path(self, public_path, path, expected):
        vite = Vite(public_path)
        assert vite._is_css_path(path) is expected

    def test_parse_attributes(self, public_path):
        vite = Vite(public_path)
        attrs = vite._parse_attributes(
            {"type": "module", "async": True, "defer": False, "nonce": None, "src": "/x.js"}
        )
        assert 'type="module"' in attrs
        assert "async" in attrs
        assert 'src="/x.js"' in attrs
        assert "defer" not in attrs
        assert all("nonce" not in a for a in attrs)

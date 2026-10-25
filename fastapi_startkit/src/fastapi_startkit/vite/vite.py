import hashlib
import json
import os
import re
import secrets
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Literal


from .exceptions import ViteException, ViteManifestNotFoundException


class Vite:
    """Generates Vite asset tags for use in templates.

    Supports both HMR (development) and manifest-based (production) modes.
    In development, a ``public/hot`` file signals that the Vite dev server is
    running; the file's contents are the HMR origin URL.
    In production, ``public/{build_directory}/manifest.json`` maps entry-point
    source paths to their hashed output files.

    Typical usage in a Jinja2 template::

        {{ vite('resources/js/app.ts') }}
        {{ vite_asset('resources/images/logo.png') }}
        {{ vite_react_refresh() }}
    """

    # Class-level manifest cache shared across all instances.
    _manifests: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        public_path: str,
        build_directory: str = "build",
        hot_file: str | None = None,
        manifest_filename: str = "manifest.json",
        asset_url: str = "",
    ) -> None:
        self._public_path = public_path
        self._build_directory = build_directory
        self._hot_file = os.path.join(public_path, hot_file or "hot")
        self._manifest_filename = manifest_filename
        # Optional base URL prefix for all generated asset URLs.
        self._asset_url = asset_url.rstrip("/")

        self._nonce: ContextVar[str | None] = ContextVar(f"vite_nonce_{id(self)}", default=None)
        self._integrity_key: str | bool = "integrity"
        self._entry_points: list[str] = []
        self._asset_path_resolver: Callable[[str], str] | None = None

        # Tag attribute resolvers (callables)
        self._script_tag_attributes_resolvers: list[Callable[..., Any]] = []
        self._style_tag_attributes_resolvers: list[Callable[..., Any]] = []
        self._preload_tag_attributes_resolvers: list[Callable[..., Any]] = []

        self._preloaded: ContextVar[dict[str, list[str]] | None] = ContextVar(
            f"vite_preloaded_assets_{id(self)}", default=None
        )

    # ------------------------------------------------------------------
    # Public configuration API
    # ------------------------------------------------------------------

    def use_csp_nonce(self, nonce: str | None = None) -> str:
        """Generate (or set) a CSP nonce applied to all generated tags."""
        value = nonce or secrets.token_hex(20)
        self._nonce.set(value)
        return value

    def csp_nonce(self) -> str | None:
        return self._nonce.get()

    def use_integrity_key(self, key: str | bool) -> "Vite":
        """Set the manifest key used to read SRI integrity hashes."""
        self._integrity_key = key
        return self

    def with_entry_points(self, entry_points: list[str]) -> "Vite":
        """Pre-configure entry points used by :meth:`to_html`."""
        self._entry_points = entry_points
        return self

    def create_asset_paths_using(self, resolver: Callable[[str], str] | None) -> "Vite":
        """Override the default asset URL builder with a custom callable."""
        self._asset_path_resolver = resolver
        return self

    def use_script_tag_attributes(self, attributes: dict[str, Any] | Callable[..., Any]) -> "Vite":
        self._script_tag_attributes_resolvers.append(self._as_resolver(attributes))
        return self

    def use_style_tag_attributes(self, attributes: dict[str, Any] | Callable[..., Any]) -> "Vite":
        self._style_tag_attributes_resolvers.append(self._as_resolver(attributes))
        return self

    def use_preload_tag_attributes(self, attributes: dict[str, Any] | bool | Callable[..., Any]) -> "Vite":
        self._preload_tag_attributes_resolvers.append(self._as_resolver(attributes))
        return self

    @staticmethod
    def _as_resolver(attributes: Any) -> Callable[..., Any]:
        if callable(attributes):
            return attributes
        return lambda *_: attributes

    # ------------------------------------------------------------------
    # Core HTML generation
    # ------------------------------------------------------------------

    def __call__(
        self,
        entrypoints: str | list[str],
        build_directory: str | None = None,
    ) -> str:
        """Return the HTML tags (preloads + stylesheets + scripts) for the given entrypoints."""
        if isinstance(entrypoints, str):
            entrypoints = [entrypoints]

        build_directory = build_directory or self._build_directory

        if self.is_running_hot():
            hot_origin = self._read_hot_origin()
            tags = [self._make_tag_for_chunk("@vite/client", f"{hot_origin}/@vite/client", None, None)]
            for ep in entrypoints:
                tags.append(self._make_tag_for_chunk(ep, f"{hot_origin}/{ep}", None, None))
            return "".join(tags)

        manifest = self._manifest(build_directory)

        tags: list[str] = []
        preloads: list[tuple[str | None, str, dict[str, Any], dict[str, Any]]] = []

        for entrypoint in entrypoints:
            chunk = self._chunk(manifest, entrypoint)

            preloads.append(
                (
                    chunk.get("src", entrypoint),
                    self._asset_path(f"{build_directory}/{chunk['file']}"),
                    chunk,
                    manifest,
                )
            )

            for import_key in self._resolve_imports(manifest, chunk):
                import_chunk = manifest[import_key]
                preloads.append(
                    (
                        import_key,
                        self._asset_path(f"{build_directory}/{import_chunk['file']}"),
                        import_chunk,
                        manifest,
                    )
                )

                for css in import_chunk.get("css", []):
                    url = self._asset_path(f"{build_directory}/{css}")
                    css_chunk = self._find_chunk_by_file(manifest, css)
                    src = css_chunk.get("src")
                    preloads.append((src, url, css_chunk, manifest))
                    tags.append(self._make_tag_for_chunk(src, url, css_chunk, manifest))

            tags.append(
                self._make_tag_for_chunk(
                    entrypoint,
                    self._asset_path(f"{build_directory}/{chunk['file']}"),
                    chunk,
                    manifest,
                )
            )

            for css in chunk.get("css", []):
                url = self._asset_path(f"{build_directory}/{css}")
                css_chunk = self._find_chunk_by_file(manifest, css)
                src = css_chunk.get("src")
                preloads.append((src, url, css_chunk, manifest))
                tags.append(self._make_tag_for_chunk(src, url, css_chunk, manifest))

        # Deduplicate while preserving insertion order.
        seen: set[str] = set()
        unique_tags: list[str] = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)

        stylesheets = [t for t in unique_tags if t.startswith("<link")]
        scripts = [t for t in unique_tags if not t.startswith("<link")]

        # Deduplicate preloads by URL, then sort CSS first.
        seen_urls: set[str] = set()
        unique_preloads: list[tuple[str | None, str, dict[str, Any], dict[str, Any]]] = []
        for p in preloads:
            url = p[1]
            if url not in seen_urls:
                seen_urls.add(url)
                unique_preloads.append(p)

        unique_preloads.sort(key=lambda p: not self._is_css_path(p[1]))

        preload_tags = [self._make_preload_tag_for_chunk(*p) for p in unique_preloads]

        return "".join(preload_tags) + "".join(stylesheets) + "".join(scripts)

    def asset(self, asset: str, build_directory: str | None = None) -> str:
        """Return the public URL for a non-entry-point asset (e.g. an image)."""
        build_directory = build_directory or self._build_directory

        if self.is_running_hot():
            return f"{self._read_hot_origin()}/{asset}"

        chunk = self._chunk(self._manifest(build_directory), asset)
        return self._asset_path(f"{build_directory}/{chunk['file']}")

    def react_refresh(self) -> str:
        """Return the React Fast Refresh preamble script (HMR mode only)."""
        if not self.is_running_hot():
            return ""

        nonce = self.csp_nonce()
        nonce_attr = f' nonce="{nonce}"' if nonce else ""
        hot_url = f"{self._read_hot_origin()}/@react-refresh"

        return (
            f'<script type="module"{nonce_attr}>\n'
            f"    import RefreshRuntime from '{hot_url}'\n"
            f"    RefreshRuntime.injectIntoGlobalHook(window)\n"
            f"    window.$RefreshReg$ = () => {{}}\n"
            f"    window.$RefreshSig$ = () => (type) => type\n"
            f"    window.__vite_plugin_react_preamble_installed__ = true\n"
            f"</script>"
        )

    def manifest_hash(self, build_directory: str | None = None) -> str | None:
        """Return an MD5 hash of the manifest file, useful for cache-busting."""
        build_directory = build_directory or self._build_directory

        if self.is_running_hot():
            return None

        path = self._manifest_path(build_directory)
        if not os.path.isfile(path):
            return None

        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def is_running_hot(self) -> bool:
        """Return True when the Vite HMR dev server is detected."""
        return os.path.isfile(self._hot_file)

    def preloaded_assets(self) -> dict[str, list[str]]:
        assets = self._preloaded.get()
        if assets is None:
            assets = {}
            self._preloaded.set(assets)
        return assets

    def flush(self) -> None:
        self._preloaded.set(None)

    def to_html(self) -> str:
        """Render pre-configured entry points as HTML (used as Htmlable)."""
        return self(self._entry_points)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_hot_origin(self) -> str:
        with open(self._hot_file) as f:
            content = f.read().strip().rstrip("/")
        return content or "http://localhost:5173"

    def _asset_path(self, path: str) -> str:
        if self._asset_path_resolver:
            return self._asset_path_resolver(path)
        if self._asset_url:
            return f"{self._asset_url}/{path.lstrip('/')}"
        return f"/{path}"

    def _manifest(self, build_directory: str) -> dict[str, Any]:
        path = self._manifest_path(build_directory)
        if path not in Vite._manifests:
            if not os.path.isfile(path):
                raise ViteManifestNotFoundException(f"Vite manifest not found at: {path}")
            with open(path) as f:
                Vite._manifests[path] = json.load(f)
        return Vite._manifests[path]

    def _manifest_path(self, build_directory: str) -> str:
        return os.path.join(self._public_path, build_directory, self._manifest_filename)

    def _chunk(self, manifest: dict[str, Any], file: str) -> dict[str, Any]:
        if file not in manifest:
            raise ViteException(f"Unable to locate file in Vite manifest: {file}")
        return manifest[file]

    def _find_chunk_by_file(self, manifest: dict[str, Any], file: str) -> dict[str, Any]:
        """Return the manifest chunk whose 'file' value matches, or a minimal stub."""
        for chunk in manifest.values():
            if chunk.get("file") == file:
                return chunk
        return {"file": file}

    def _resolve_imports(
        self,
        manifest: dict[str, Any],
        chunk: dict[str, Any],
        seen: dict[str, bool] | None = None,
    ) -> list[str]:
        if seen is None:
            seen = {}
        imports: list[str] = []
        for import_key in chunk.get("imports", []):
            if import_key in seen:
                continue
            seen[import_key] = True
            imports.append(import_key)
            if import_key in manifest:
                imports.extend(self._resolve_imports(manifest, manifest[import_key], seen))
        return imports

    def _make_tag_for_chunk(
        self,
        src: str | None,
        url: str,
        chunk: dict[str, Any] | None,
        manifest: dict[str, Any] | None,
    ) -> str:
        if self._is_css_path(url):
            return self._make_stylesheet_tag_with_attributes(
                url,
                self._resolve_stylesheet_tag_attributes(src, url, chunk, manifest),
            )
        return self._make_script_tag_with_attributes(
            url,
            self._resolve_script_tag_attributes(src, url, chunk, manifest),
        )

    def _make_preload_tag_for_chunk(
        self,
        src: str | None,
        url: str,
        chunk: dict[str, Any],
        manifest: dict[str, Any],
    ) -> str:
        attributes = self._resolve_preload_tag_attributes(src, url, chunk, manifest)
        if attributes is False:
            return ""

        self.preloaded_assets()[url] = self._parse_attributes({k: v for k, v in attributes.items() if k != "href"})
        return f"<link {' '.join(self._parse_attributes(attributes))} />"

    def _resolve_script_tag_attributes(self, src, url, chunk, manifest) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self._integrity_key is not False:
            attrs["integrity"] = (chunk or {}).get(self._integrity_key, False)
        for resolver in self._script_tag_attributes_resolvers:
            attrs.update(resolver(src, url, chunk, manifest))
        return attrs

    def _resolve_stylesheet_tag_attributes(self, src, url, chunk, manifest) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self._integrity_key is not False:
            attrs["integrity"] = (chunk or {}).get(self._integrity_key, False)
        for resolver in self._style_tag_attributes_resolvers:
            attrs.update(resolver(src, url, chunk, manifest))
        return attrs

    def _resolve_preload_tag_attributes(self, src, url, chunk, manifest) -> dict[str, Any] | Literal[False]:
        if self._is_css_path(url):
            attrs = {
                "rel": "preload",
                "as": "style",
                "href": url,
                "nonce": self.csp_nonce() or False,
                "crossorigin": self._resolve_stylesheet_tag_attributes(src, url, chunk, manifest).get(
                    "crossorigin", False
                ),
            }
        else:
            attrs = {
                "rel": "modulepreload",
                "href": url,
                "nonce": self.csp_nonce() or False,
                "crossorigin": self._resolve_script_tag_attributes(src, url, chunk, manifest).get("crossorigin", False),
            }

        if self._integrity_key is not False:
            attrs["integrity"] = (chunk or {}).get(self._integrity_key, False)

        for resolver in self._preload_tag_attributes_resolvers:
            resolved = resolver(src, url, chunk, manifest)
            if resolved is False:
                return False
            attrs.update(resolved)

        return attrs

    def _make_script_tag_with_attributes(self, url: str, attributes: dict[str, Any]) -> str:
        attrs = self._parse_attributes(
            {
                "type": "module",
                "src": url,
                "nonce": self.csp_nonce() or False,
                **attributes,
            }
        )
        return f"<script {' '.join(attrs)}></script>"

    def _make_stylesheet_tag_with_attributes(self, url: str, attributes: dict[str, Any]) -> str:
        attrs = self._parse_attributes(
            {
                "rel": "stylesheet",
                "href": url,
                "nonce": self.csp_nonce() or False,
                **attributes,
            }
        )
        return f"<link {' '.join(attrs)} />"

    def _is_css_path(self, path: str) -> bool:
        return bool(
            re.search(
                r"\.(css|less|sass|scss|styl|stylus|pcss|postcss)(\?[^.]*)?$",
                path,
            )
        )

    def _parse_attributes(self, attributes: dict[str, Any]) -> list[str]:
        result: list[str] = []
        for key, value in attributes.items():
            if value in (False, None):
                continue
            if value is True:
                result.append(str(key))
            else:
                result.append(f'{key}="{value}"')
        return result

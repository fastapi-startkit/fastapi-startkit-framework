from contextlib import AbstractContextManager
from typing import Callable, Optional

class Vite:
    """Facade for the Vite asset helper.

    Generates ``<script>`` / ``<link>`` tags from the Vite manifest and
    provides HMR support when the Vite dev server is running.
    """

    @staticmethod
    def __call__(
        entrypoints: str | list[str],
        build_directory: Optional[str] = None,
    ) -> str:
        """Return preload + stylesheet + script tags for *entrypoints*."""
        ...

    @staticmethod
    def asset(asset: str, build_directory: Optional[str] = None) -> str:
        """Return the public URL for a non-entry-point asset (e.g. an image)."""
        ...

    @staticmethod
    def react_refresh() -> str:
        """Return the React Fast Refresh preamble script (HMR mode only)."""
        ...

    @staticmethod
    def is_running_hot() -> bool:
        """Return ``True`` when the Vite HMR dev server hot-file is present."""
        ...

    @staticmethod
    def use_csp_nonce(nonce: Optional[str] = None) -> str:
        """Generate (or set) a CSP nonce applied to all generated tags."""
        ...

    @staticmethod
    def csp_nonce() -> Optional[str]:
        """Return the current CSP nonce."""
        ...

    @staticmethod
    def use_integrity_key(key: str | bool) -> "Vite":
        """Set the manifest key used to read SRI integrity hashes."""
        ...

    @staticmethod
    def with_entry_points(entry_points: list[str]) -> "Vite":
        """Pre-configure entry points used by :meth:`to_html`."""
        ...

    @staticmethod
    def create_asset_paths_using(resolver: Optional[Callable[[str], str]]) -> "Vite":
        """Override the default asset URL builder with a custom callable."""
        ...

    @staticmethod
    def use_script_tag_attributes(attributes: dict | Callable) -> "Vite":
        """Register extra attributes for generated ``<script>`` tags."""
        ...

    @staticmethod
    def use_style_tag_attributes(attributes: dict | Callable) -> "Vite":
        """Register extra attributes for generated ``<link rel=stylesheet>`` tags."""
        ...

    @staticmethod
    def use_preload_tag_attributes(attributes: dict | bool | Callable) -> "Vite":
        """Register extra attributes (or suppression) for generated preload tags."""
        ...

    @staticmethod
    def manifest_hash(build_directory: Optional[str] = None) -> Optional[str]:
        """Return an MD5 hash of the manifest file (useful for cache-busting)."""
        ...

    @staticmethod
    def preloaded_assets() -> dict:
        """Return the set of assets that have already been preloaded this request."""
        ...

    @staticmethod
    def flush() -> None:
        """Reset per-request state (call after each response in long-running servers)."""
        ...

    @staticmethod
    def request_scope() -> AbstractContextManager[None]: ...
    @staticmethod
    def to_html() -> str:
        """Render pre-configured entry points as an HTML string."""
        ...

from typing import Callable, Any
from jinja2 import PackageLoader, BaseLoader

class View:
    """View facade."""

    @staticmethod
    def render(template: str, dictionary: dict = {}) -> "View":
        """Render the given template name with the given context as string."""
        ...
    @staticmethod
    def get_content() -> str:
        """Get the rendered content as string."""
        ...
    @staticmethod
    def hydrate_from_composers():
        """Add data into the view from specified composers."""
        ...
    @staticmethod
    def composer(composer_name: str, dictionary: dict) -> "View":
        """Add/Update composer with the given name and data."""
        ...
    @staticmethod
    def share(dictionary: dict) -> "View":
        """Share data to all templates."""
        ...
    @staticmethod
    def exists(template: str) -> bool:
        """Check if a template with the given name exists."""
        ...
    @staticmethod
    def add_location(template_location: str, loader: type[BaseLoader] = PackageLoader):
        """Add location directory from which view templates can be loaded. The Jinja2 loader type
        can be specified."""
        ...
    @staticmethod
    def add_namespaced_location(namespace: str, template_location: str):
        """Add namespaced location directory from which view templates can be loaded."""
        ...
    @staticmethod
    def add_from_package(package_name: str, path_in_package: str): ...
    @staticmethod
    def filter(name: str, function: Callable):
        """Add filter functions to views with the given name."""
        ...
    @staticmethod
    def add_extension(extension: str) -> "View":
        """Register Jinja2 extension to views."""
        ...
    @staticmethod
    def load_template(template: str):
        """Private method for loading all the locations into the current environment."""
        ...
    @staticmethod
    def get_current_loaders():
        """Get all enabled Jinja2 loaders."""
        ...
    @staticmethod
    def set_separator(token: str) -> "View":
        """Change separator for view names (default is /)."""
        ...
    @staticmethod
    def set_file_extension(extension: str) -> "View":
        """Change file view extension (default is .html)."""
        ...
    @staticmethod
    def get_response() -> str:
        """Get the rendered content as string."""
        ...
    @staticmethod
    def test(key: str, obj: Any) -> "View": ...

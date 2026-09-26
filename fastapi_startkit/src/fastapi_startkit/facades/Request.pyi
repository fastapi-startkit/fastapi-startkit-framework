from typing import Any

Route = Any

class Request:
    """Request facade."""

    @staticmethod
    def load():
        """Load request from environment."""
        ...
    @staticmethod
    def load_params(params: dict | None = None):
        """Load request parameters."""
        ...
    @staticmethod
    def param(param: str, default: str = "") -> str:
        """Get query string parameter from request."""
        ...
    @staticmethod
    def get_route() -> "Route":
        """Get Route associated to request if any."""
        ...
    @staticmethod
    def get_path() -> str:
        """Get request path (read from PATH_INFO) environment variable without eventual query
        string parameters."""
        ...
    @staticmethod
    def get_path_with_query() -> str:
        """Get request path (read from PATH_INFO) environment variable with eventual query
        string parameters."""
        ...
    @staticmethod
    def get_back_path() -> str:
        """Get previous request path if it has been defined as '__back' input."""
        ...
    @staticmethod
    def get_request_method() -> str:
        """Get request method (read from REQUEST_METHOD environment variable)."""
        ...
    @staticmethod
    def input(name: str, default: str = "") -> str:
        """Get a specific request input value with the given name. If the value does not exist in
        the request return the default value."""
        ...
    @staticmethod
    def cookie(name: str, value: str | None = None, **options) -> None:
        """If no value provided, read the cookie value with the given name from the request. Else
        create a cookie in the request with the given name and value.
        Some options can be passed when creating cookie, refer to CookieJar class."""
        ...
    @staticmethod
    def delete_cookie(name: str) -> "Request":
        """Delete cookie with the given name from the request."""
        ...
    @staticmethod
    def header(name: str, value: str | None = None) -> "str|None":
        """If no value provided, read the header value with the given name from the request. Else
        add a header in the request with the given name and value."""
        ...
    @staticmethod
    def all() -> dict:
        """Get all inputs from the request as a dictionary."""
        ...
    @staticmethod
    def only(*inputs: str) -> dict:
        """Get only the given inputs from the request as a dictionary."""
        ...
    @staticmethod
    def old(key: str):
        """Get value from session for the given key."""
        ...
    @staticmethod
    def is_not_safe() -> bool:
        """Check if the current request is considered 'safe', meaning that the request method is
        GET, OPTIONS or HEAD."""
        ...
    @staticmethod
    def user() -> "None|Any":
        """Get the current authenticated user if any. LoadUserMiddleware needs to be used for user
        to be populated in request."""
        ...
    @staticmethod
    def set_user(user: Any) -> "Request":
        """Set the current authenticated user of the request."""
        ...
    @staticmethod
    def remove_user() -> "Request":
        """Log out user of the current request."""
        ...
    @staticmethod
    def contains(route: str) -> bool:
        """Check if current request path match the given URL."""
        ...
    @staticmethod
    def get_subdomain(exclude_www: bool = True) -> "None|str":
        """Get the request subdomain if subdomains are enabled."""
        ...
    @staticmethod
    def get_host() -> str:
        """Get the request host (from HTTP_HOST environment variable)."""
        ...
    @staticmethod
    def activate_subdomains():
        """Enable subdomains for this request."""
        ...
    @staticmethod
    def is_ajax() -> bool:
        """Check if the current request is an AJAX request."""
        ...

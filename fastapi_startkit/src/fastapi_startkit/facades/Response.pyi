from typing import Any

class Response:
    """Response facade."""

    @staticmethod
    def json(payload: Any, status: int = 200) -> bytes:
        """Set the response as a JSON response."""
        ...
    @staticmethod
    def make_headers(content_type: str = "text/html; charset=utf-8") -> None:
        """Recompute Content-Length of the response after modyifing it."""
        ...
    @staticmethod
    def header(name: str, value: str | None = None) -> "None|str":
        """Get response header for the given name if no value provided or add headers to response."""
        ...
    @staticmethod
    def get_headers() -> list:
        """Get all response headers."""
        ...
    @staticmethod
    def cookie(name: str, value: str | None = None, **options) -> "None|str":
        """Get response cookie for the given name if no value provided or add cookie to
        the response with the given name, value and options."""
        ...
    @staticmethod
    def delete_cookie(name: str) -> "Response":
        """Delete the cookie with the given name from the response."""
        ...
    @staticmethod
    def get_response_content() -> bytes:
        """Get response content."""
        ...
    @staticmethod
    def status(status: "str|int") -> "Response":
        """Set HTTP status code of the response."""
        ...
    @staticmethod
    def is_status(code: int) -> bool:
        """Check if response has the given status code."""
        ...
    @staticmethod
    def get_status_code() -> str:
        """Gets the HTTP status code of the response as a human string, like "200 OK"."""
        ...
    @staticmethod
    def get_status(): ...
    @staticmethod
    def data() -> bytes:
        """Get the response content as bytes."""
        ...
    @staticmethod
    def converted_data() -> "str|bytes":
        """Get the response content as string or bytes so that the WSGI server handles it."""
        ...
    @staticmethod
    def view(view: Any, status: int = 200) -> "bytes|Response":
        """Set the response as a string or view."""
        ...
    @staticmethod
    def back() -> "Response":
        """Set the response as a redirect response back to previous path defined from the
        request."""
        ...
    @staticmethod
    def redirect(
        location: str | None = None,
        name: str | None = None,
        params: dict = {},
        url: str | None = None,
        status: int = 302,
    ) -> "Response":
        """Set the response as a redirect response. The redirection location can be defined
        with the location URL or with a route name. If a route name is used, route params can
        be provided."""

        ...
    @staticmethod
    def to_bytes() -> "bytes":
        """Converts the response to bytes."""
        ...
    @staticmethod
    def download(name: str, location: str, force: bool = False) -> "Response":
        """Set the response as a file download response."""
        ...

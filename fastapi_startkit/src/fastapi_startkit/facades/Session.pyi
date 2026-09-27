from typing import Any

class Session:
    """Session facade."""

    @staticmethod
    def add_driver(name: str, driver: Any) -> None:
        """Register a new session driver with the given name."""
        ...
    @staticmethod
    def driver(driver: str) -> Any:
        """Get a registered session driver with the given name."""
        ...
    @staticmethod
    def set_configuration(config: dict) -> "Session":
        """Set session driver options."""
        ...
    @staticmethod
    def get_driver(name: str | None = None) -> Any:
        """Get the default session driver or the driver with the given name."""
        ...
    @staticmethod
    def get_config_options(driver: str | None = None) -> dict:
        """Get the options of the default session driver or of the driver with the given name."""
        ...
    @staticmethod
    def start(driver: str | None = None) -> "Session":
        """Initialize session."""
        ...
    @staticmethod
    def get_data() -> dict:
        """Get all session data."""
        ...
    @staticmethod
    def save(driver: str | None = None) -> None:
        """Save session data for the default session driver or the given named driver."""
        ...
    @staticmethod
    def set(key: str, value: Any) -> None:
        """Save value in default session."""
        ...
    @staticmethod
    def increment(key: str, count: int = 1) -> None:
        """Increment session key with given count."""
        ...
    @staticmethod
    def decrement(key: str, count: int = 1) -> None:
        """Decrement session key with given count."""
        ...
    @staticmethod
    def has(key: str) -> bool:
        """Check if key is present in default session."""
        ...
    @staticmethod
    def get(key: str) -> Any:
        """Get value of the given key in default session."""
        ...
    @staticmethod
    def pull(key: str) -> Any:
        """Get and remove value for the given key in session."""
        ...
    @staticmethod
    def flush() -> None:
        """Delete all keys from session."""
        ...
    @staticmethod
    def delete(key: str) -> "None|Any":
        """Delete the given key from session."""
        ...
    @staticmethod
    def flash(key: str, value: Any) -> None:
        """Save temporary value into session."""
        ...
    @staticmethod
    def all() -> dict:
        """Get all session data."""
        ...

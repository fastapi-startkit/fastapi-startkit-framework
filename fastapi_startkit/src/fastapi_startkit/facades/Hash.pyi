from typing import Any

class Hash:
    @staticmethod
    def add_driver(name: str, driver: Any): ...
    @staticmethod
    def set_configuration(config: dict) -> "Hash": ...
    @staticmethod
    def get_driver(name: str | None = None) -> Any: ...
    @staticmethod
    def get_config_options(driver: str | None = None) -> dict: ...
    @staticmethod
    def make(string: str, options: dict = {}, driver: str | None = None) -> str:
        """Hash a string and return as string based on configured hashing protocol."""
        ...
    @staticmethod
    def make_bytes(string: str, options: dict = {}, driver: str | None = None) -> bytes:
        """Hash a string and return as bytes based on configured hashing protocol."""
        ...
    @staticmethod
    def check(
        plain_string: str,
        hashed_string: str,
        options: dict = {},
        driver: str | None = None,
    ) -> bool:
        """Verify that a given string matches its hashed version (based on configured hashing protocol)."""
        ...
    @staticmethod
    def needs_rehash(hashed_string: str, options: dict = {}, driver: str | None = None) -> bool:
        """Verify that a given hash needs to be hashed again because parameters for generating
        the hash have changed."""
        ...

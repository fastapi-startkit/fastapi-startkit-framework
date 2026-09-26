from typing import Callable, List, Tuple, Any

AuthorizationResponse = Any
Policy = Any
GateObject = Any

class Gate:
    """Gate facade."""

    @staticmethod
    def define(permission: str, condition: Callable): ...
    @staticmethod
    def register_policies(policies: List[Tuple[Any, Policy]]) -> "Gate": ...
    @staticmethod
    def get_policy_for(instance_or_class: "str|Any") -> "None|Policy": ...
    @staticmethod
    def before(before_callback: Callable): ...
    @staticmethod
    def after(after_callback: Callable): ...
    @staticmethod
    def allows(permission: str, *args) -> bool: ...
    @staticmethod
    def denies(permission, *args) -> bool: ...
    @staticmethod
    def has(permission: str) -> bool: ...
    @staticmethod
    def for_user(user: Any) -> GateObject: ...
    @staticmethod
    def any(permissions: List[str], *args) -> bool:
        """Check that every of those permissions are allowed."""
        ...
    @staticmethod
    def none(permissions: List[str], *args) -> bool:
        """Check that none of those permissions are allowed."""
        ...
    @staticmethod
    def authorize(permission: str, *args) -> bool: ...
    @staticmethod
    def inspect(permission: str, *args) -> "bool|AuthorizationResponse":
        """Get permission checks results for the given user then builds and returns an
        authorization response."""
        ...
    @staticmethod
    def check(permission: str, *args):
        """The core of the authorization class. Run before() checks, permission check and then
        after() checks."""
        ...

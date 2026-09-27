from typing import Any, Callable

Limiter = Any

class RateLimiter:
    """Rate Limiter facades to add rate limiting to your functions."""

    @staticmethod
    def register(name: str, callback: "Limiter") -> "RateLimiter":
        """Register a new rate limiter with the given name"""
        ...
    @staticmethod
    def attempts(key: str) -> int:
        """Get number of attempts left for a given rate limiter key."""
        ...
    @staticmethod
    def get_limiter(name: str) -> "Limiter":
        """Get rate limiter registered with the given name."""
        ...
    @staticmethod
    def attempt(key: str, callback: Callable, max_attempts: int, delay: int = 60) -> Any:
        """Try to execute the given callback if not limited by the 'key' rate limiter."""
        ...
    @staticmethod
    def too_many_attempts(key: str, max_attempts: int) -> bool:
        """Check if given rate limiter key got more (or equal) attempts than max_attempts."""
        ...
    @staticmethod
    def hit(key: str, delay: int) -> int:
        """Add one attempt for the given key."""
        ...
    @staticmethod
    def reset_attempts(key: str) -> bool:
        """Reset attempts count to 0 for the given key."""
        ...
    @staticmethod
    def clear(key: str):
        """Clear all data of the given rate limiter key."""
        ...
    @staticmethod
    def available_at(key: str) -> int:
        """Get UNIX integer timestamp at which rate limiter key will be available again."""
        ...
    @staticmethod
    def available_in(key: str) -> int:
        """Get seconds in which rate limiter key will be available again."""
        ...
    @staticmethod
    def remaining(key: str, max_attempts: int) -> int:
        """Get remaining attempts before given rate limiter key is limited regarding max_attempts limit."""
        ...

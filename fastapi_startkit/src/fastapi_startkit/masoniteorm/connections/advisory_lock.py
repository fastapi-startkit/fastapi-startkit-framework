import hashlib

BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1
LOCK_TIMEOUT_MAX_MS = 2**31 - 1
LOCK_NOT_AVAILABLE = "55P03"


def advisory_lock_key(key: str | int) -> int:
    if isinstance(key, str):
        digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big", signed=True)
    if isinstance(key, bool) or not isinstance(key, int):
        raise TypeError(f"Advisory lock key must be a str or int, got {type(key).__name__}")
    if not BIGINT_MIN <= key <= BIGINT_MAX:
        raise ValueError(f"Advisory lock key {key} is outside the bigint range")
    return key


def lock_timeout_value(timeout_ms: int) -> str:
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise TypeError(f"lock_timeout must be an int number of milliseconds, got {type(timeout_ms).__name__}")
    if not 0 <= timeout_ms <= LOCK_TIMEOUT_MAX_MS:
        raise ValueError(f"lock_timeout must be between 0 and {LOCK_TIMEOUT_MAX_MS} milliseconds, got {timeout_ms}")
    return str(timeout_ms)

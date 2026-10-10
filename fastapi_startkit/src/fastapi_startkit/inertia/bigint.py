from typing import Any

MAX_SAFE_INTEGER = 2**53 - 1
BIG_INTEGER_KEY = "$bigint"


def encode_big_integers(value: Any) -> Any:
    if isinstance(value, int):
        return {BIG_INTEGER_KEY: str(value)} if abs(value) > MAX_SAFE_INTEGER else value
    if isinstance(value, dict):
        return {key: encode_big_integers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_big_integers(item) for item in value]
    return value

import json
from typing import Any

HTML_UNSAFE_CHARACTERS = str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})


def html_safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True).translate(HTML_UNSAFE_CHARACTERS)


MAX_SAFE_INTEGER = 2**53 - 1
BIG_INTEGER_KEY = "$bigint"


def encode_big_integers(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return {BIG_INTEGER_KEY: str(value)} if abs(value) > MAX_SAFE_INTEGER else value
    if isinstance(value, dict):
        return {key: encode_big_integers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_big_integers(item) for item in value]
    return value

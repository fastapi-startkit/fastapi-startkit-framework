import json
from typing import Any

HTML_UNSAFE_CHARACTERS = str.maketrans(
    {
        "<": "\\u003c",
        ">": "\\u003e",
        "&": "\\u0026",
        " ": "\\u2028",
        " ": "\\u2029",
    }
)


def html_safe_json(value: Any) -> str:
    return json.dumps(value).translate(HTML_UNSAFE_CHARACTERS)

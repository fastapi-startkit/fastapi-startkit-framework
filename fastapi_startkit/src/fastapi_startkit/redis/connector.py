from typing import Any


class RedisNotInstalledError(ImportError):
    def __init__(self) -> None:
        super().__init__(
            "Redis support requires the 'redis' package. Install it with: pip install 'fastapi-startkit[redis]'"
        )


def connect(parameters: dict[str, Any]) -> Any:
    try:
        from redis.asyncio import Redis
    except ImportError as error:
        raise RedisNotInstalledError() from error

    parameters = dict(parameters)
    url = parameters.pop("url", None)
    if url:
        return Redis.from_url(url, **parameters)
    return Redis(**parameters)

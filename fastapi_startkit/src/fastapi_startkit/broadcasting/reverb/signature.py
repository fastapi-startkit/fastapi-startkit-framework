import hashlib
import hmac
import re

from typing_extensions import TypeIs

SOCKET_ID = re.compile(r"[0-9]+\.[0-9]+", re.ASCII)
CHANNEL_NAME = re.compile(r"[A-Za-z0-9_\-=@,.;]{1,200}", re.ASCII)


def valid_socket_id(socket_id: object) -> TypeIs[str]:
    return isinstance(socket_id, str) and SOCKET_ID.fullmatch(socket_id) is not None


def valid_channel(channel: object) -> TypeIs[str]:
    return isinstance(channel, str) and CHANNEL_NAME.fullmatch(channel) is not None


def requires_auth(channel: object) -> bool:
    return isinstance(channel, str) and channel.startswith(("private-", "presence-"))


def is_presence(channel: str) -> bool:
    return channel.startswith("presence-")


def sign(key: str, secret: str, socket_id: str, channel: str, channel_data: str | None = None) -> str:
    parts = [socket_id, channel] if channel_data is None else [socket_id, channel, channel_data]
    digest = hmac.new(secret.encode(), ":".join(parts).encode(), hashlib.sha256).hexdigest()
    return f"{key}:{digest}"


def verify(key: str, secret: str, socket_id: str, channel: str, auth: object, channel_data: object = None) -> bool:
    if not secret or not isinstance(auth, str):
        return False
    if not valid_socket_id(socket_id) or not valid_channel(channel) or not requires_auth(channel):
        return False
    if not is_presence(channel):
        channel_data = None
    elif not isinstance(channel_data, str):
        return False
    expected = sign(key, secret, socket_id, channel, channel_data)
    return hmac.compare_digest(auth.encode(), expected.encode())

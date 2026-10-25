import hashlib
import hmac


def requires_auth(channel: object) -> bool:
    return isinstance(channel, str) and channel.startswith(("private-", "presence-"))


def sign(key: str, secret: str, socket_id: str, channel: str, channel_data: str | None = None) -> str:
    parts = [socket_id, channel] if channel_data is None else [socket_id, channel, channel_data]
    digest = hmac.new(secret.encode(), ":".join(parts).encode(), hashlib.sha256).hexdigest()
    return f"{key}:{digest}"


def verify(key: str, secret: str, socket_id: str, channel: str, auth: object, channel_data: object = None) -> bool:
    if not isinstance(auth, str) or not (channel_data is None or isinstance(channel_data, str)):
        return False
    expected = sign(key, secret, socket_id, channel, channel_data)
    return hmac.compare_digest(auth.encode(), expected.encode())

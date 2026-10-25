# 035. Signed private-channel subscriptions and a reachable /broadcasting/auth

Date: 2026-10-25

## Problem

Two defects in `fastapi_startkit.broadcasting`:

- **F4, auth bypass.** `ReverbServer` subscribed every socket to any channel named in `pusher:subscribe`, including `private-*` and `presence-*`. The `auth` field was never checked, so any WebSocket client received private broadcasts without calling `/broadcasting/auth`. The endpoint also returned `{"auth": true}` rather than a Pusher signature, so a real Echo client could not have been verified even with a check in place.
- **F3, 404.** `ReverbProvider` mounted the WebSocket app with `fastapi_app.mount("", ...)` before adding `POST /broadcasting/auth`. Starlette tries routes in order and an empty-path `Mount` matches every path, so the auth route, and every route registered after the provider boots, returned the inner app's 404. The endpoint also used a function-local `Request` import under `from __future__ import annotations`, so FastAPI could not resolve the annotation and would have treated `request` as a query parameter.

## Alternatives

1. Track authorised `(socket_id, channel)` pairs in server memory when `/broadcasting/auth` succeeds and check them on subscribe. This is not the Pusher protocol, so it breaks Echo, and it fails with more than one worker.
2. Use the Pusher protocol: `/broadcasting/auth` returns `key:HMAC-SHA256(secret, "socket_id:channel[:channel_data]")` and the server recomputes the signature on subscribe. This is stateless, works across workers and matches what Laravel Echo sends.

For F3, keep the mount and register it last, or register plain routes on the FastAPI router. Ordering cannot be guaranteed, because application routes can be added after any provider boots.

## Decision

Option 2 for F4, and plain routes for F3.

## Implementation

- `broadcasting/reverb/signature.py`: `requires_auth(channel)`, `sign(key, secret, socket_id, channel, channel_data=None)` and `verify(...)`, which compares with `hmac.compare_digest` and rejects non-string `auth` or `channel_data`.
- `ReverbServer(key, secret)`: on a `private-`/`presence-` subscribe with a missing or invalid signature it sends `pusher:subscription_error` (`status: 401`) and does not subscribe the socket. Public channels are unchanged.
- `ReverbProvider.register` builds the server from `broadcasting.connections.reverb.key`/`secret`.
- `ReverbProvider` registers `/app/{key}` with `router.add_websocket_route` and `/broadcasting/auth` with `router.add_route`, a Starlette endpoint, so neither depends on route order or annotation resolution.
- `/broadcasting/auth` requires string `channel_name` and `socket_id` (422 otherwise) and returns 403 when the channel callback denies. On success it returns `{"auth": signature}`. Presence channels also return `channel_data` (`{"user_id": "<user.id>"}`), which is included in the signature.

## Validation

- Tests drive the fully booted app through `TestClient`: the auth route and routes added after boot are reachable whatever the provider order. A private subscribe without a signature is rejected and receives no broadcasts. Forged, wrong-socket, wrong-secret and non-string signatures are rejected. A signature obtained from `/broadcasting/auth` subscribes and receives broadcasts. Tampered presence `channel_data` is rejected.
- Full suite: `uv run pytest --ignore=tests/masoniteorm/postgres`.

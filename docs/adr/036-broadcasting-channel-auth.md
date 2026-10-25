# 036. Signed private-channel subscriptions and a reachable /broadcasting/auth

Date: 2026-10-25

## Problem

Two defects in `fastapi_startkit.broadcasting`:

- **F4, auth bypass.** `ReverbServer` subscribed every socket to any channel named in `pusher:subscribe`, including `private-*` and `presence-*`. The `auth` field was never checked, so any WebSocket client received private broadcasts without calling `/broadcasting/auth`. The endpoint also returned `{"auth": true}` rather than a Pusher signature, so a real Echo client could not have been verified even with a check in place.
- **F3, 404.** `ReverbProvider` mounted the WebSocket app with `fastapi_app.mount("", ...)` before adding `POST /broadcasting/auth`. Starlette tries routes in order and an empty-path `Mount` matches every path, so the auth route, and every route registered after the provider boots, returned the inner app's 404. The endpoint also used a function-local `Request` import under `from __future__ import annotations`, so FastAPI could not resolve the annotation and would have treated `request` as a query parameter.

The security review of the first fix found more problems:

- **Signature confusion (critical).** The signed string is `socket_id:channel[:channel_data]`, joined with `:`. The endpoint accepted any `socket_id`, signed public channels for anonymous users, and the server verified client `channel_data` for `private-` channels as well. An anonymous client with socket id `R` could request a signature for channel `news` with `socket_id=R:private-orders.1`, which is the HMAC of `R:private-orders.1:news`, then subscribe to `private-orders.1` with `channel_data: "news"`. `presence-` channels fell the same way.
- **Default secret (high).** `REVERB_APP_SECRET` defaulted to `"secret"`, so anyone could mint signatures for an unconfigured deployment.
- **Malformed frames (medium).** A non-JSON frame or a non-object `data` raised inside the handler. Only `WebSocketDisconnect` triggered cleanup, so each crashed socket stayed in `ConnectionManager` and `ChannelManager` forever. The frame size limit was the ASGI server's default (16 MB in uvicorn).
- **Low.** A JSON body that is not an object returned 500. Presence auth signed `user_id: ""` when the callback allowed a `None` user.

## Threat model

The attacker is any network client. It can open WebSockets, call `/broadcasting/auth` with or without a session, and send arbitrary frames. It does not know `REVERB_APP_SECRET`. Two things must hold. A socket can join a `private-`/`presence-` channel only with a signature that the server issued for that socket, that channel and, for presence, that `channel_data`. Malformed traffic must not crash the handler or grow server memory.

## Alternatives

1. Track authorised `(socket_id, channel)` pairs in server memory when `/broadcasting/auth` succeeds and check them on subscribe. This is not the Pusher protocol, so it breaks Echo, and it fails with more than one worker.
2. Use the Pusher protocol: `/broadcasting/auth` returns `key:HMAC-SHA256(secret, "socket_id:channel[:channel_data]")` and the server recomputes the signature on subscribe. This is stateless, works across workers and matches what Laravel Echo sends.

For the confusion, a length-prefixed or JSON-encoded signing string would remove the ambiguity, but pusher-js and Laravel's broadcasters compute the colon-joined form, so changing it breaks compatibility. Instead, constrain each part so that `:` can only be a separator.

For F3, keep the mount and register it last, or register plain routes on the FastAPI router. Ordering cannot be guaranteed, because application routes can be added after any provider boots.

## Decision

Option 2 for F4, plain routes for F3, and the Pusher wire format kept as is with every signed part validated.

## Implementation

- `broadcasting/reverb/signature.py`:
  - `valid_socket_id` accepts only ASCII `^[0-9]+\.[0-9]+$`, Pusher's format.
  - `valid_channel` accepts only Pusher channel names: 1 to 200 characters from `A-Za-z0-9_-=@,.;`. A `:` is never allowed.
  - `verify` returns false when the secret is empty, when the socket id or channel is invalid, or when the channel is not `private-`/`presence-`. It includes `channel_data` only for `presence-` channels, where it is required, and ignores it for `private-`. It compares with `hmac.compare_digest`.
- `ConnectionManager` issues socket ids as `<random>.<random>` from `secrets.randbelow`. The server always verifies against the subscribing connection's own id.
- `ReverbServer`:
  - On a `private-`/`presence-` subscribe with a missing or invalid signature it sends `pusher:subscription_error` (`AuthError`, 401). An invalid channel name gets `InvalidChannel`, 400. In both cases the socket is not subscribed.
  - Frames that are binary, not JSON, not an object, or that have a non-string `event` or a malformed subscribe `data` get `pusher:error` (code 4200), and the connection stays open.
  - A text frame larger than `max_message_size` (10 000 characters, Pusher's message limit) gets `pusher:error` and the connection is closed with 1009. Operators should also set the ASGI server's limit (`uvicorn --ws-max-size`) so oversized frames are rejected before they are buffered.
  - The connection and its subscriptions are removed in a `finally`, whatever ends the loop. `ChannelManager` deletes channels with no subscribers.
- `/broadcasting/auth`:
  - Malformed JSON returns 400. A body that is not an object returns 422. An invalid `socket_id` or `channel_name` returns 422.
  - Returns 403 when the channel is not `private-`/`presence-` (as Laravel does), when there is no authenticated user, when the server has no secret, or when the channel callback denies.
  - Presence returns 403 if the user has no `id`, and otherwise signs `channel_data` `{"user_id": "<id>"}`.
- Secret: `REVERB_APP_SECRET` has no default. `ReverbProvider.register` raises `RuntimeError` when the secret is empty or `"secret"` and `APP_ENV` is not `local` or `testing`. In local and testing an empty secret boots, but every `private-`/`presence-` subscription and auth request is rejected.
- `ReverbProvider` registers `/app/{key}` with `router.add_websocket_route` and `/broadcasting/auth` with `router.add_route`, a Starlette endpoint, so neither depends on route order or annotation resolution.

The endpoint accepts form posts. A cross-site page can send one, but it cannot read the signature unless CORS is permissive, so no CSRF token is required. `pusher:unsubscribe` and `client-*` events remain unimplemented (unchanged); `client-*` events are dropped, so nothing leaks.

## Validation

- Tests drive the fully booted app through `TestClient`. The auth route and routes added after boot are reachable whatever the provider order. A private subscribe without a signature is rejected and receives no broadcasts. Forged, wrong-socket, wrong-secret and non-string signatures are rejected, as is tampered presence `channel_data`.
- Regression tests replay the reviewer's attack against `private-orders.1` and `presence-room.vip`. Before this change they ended in `subscription_succeeded`. Further tests cover a self-signed private signature over `socket:channel:data`, malformed socket ids and channel names on both auth and subscribe, 403 for public channels and anonymous users, and 400/422 bodies.
- Secret tests cover the empty default, refusing to boot in `production` with an unset, empty or `"secret"` value, booting in local and testing, and rejecting every protected subscription when the secret is empty.
- Server tests cover each malformed frame shape (error reply, connection kept), oversized frames (close 1009), and cleanup after malformed frames and after a handler exception.
- Full suite: `uv run pytest --ignore=tests/masoniteorm/postgres --cov`.

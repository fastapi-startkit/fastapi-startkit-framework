---
name: broadcasting
description: WebSocket event broadcasting via Reverb — define events, emit to channels, authorize subscribers.
---

# Broadcasting

The broadcasting module lets you push real-time events from the server to connected WebSocket clients using the Reverb driver (Pusher protocol). Use it whenever you need live updates — order status, notifications, presence indicators, chat messages — without polling.

## When to use

- Notify a user that their background job completed
- Push live order-status updates to a dashboard
- Show who else is viewing a page (presence channels)
- Fan-out notifications to a group of authenticated users

## Defining an event

Subclass `BroadcastEvent`, implement `broadcast_on()` to declare target channels, and set `payload` with the data to send:

```python
from fastapi_startkit.broadcasting import BroadcastEvent, PrivateChannel

class OrderShipped(BroadcastEvent):
    def __init__(self, order_id: int) -> None:
        self.payload = {"order_id": order_id, "status": "shipped"}

    def broadcast_on(self) -> list:
        return [PrivateChannel(f"orders.{self.payload['order_id']}")]
```

- `broadcast_on()` must return a list of `Channel`, `PrivateChannel`, or `PresenceChannel` objects.
- `payload` (dict) is what subscribers receive. Defaults to `{}`.
- The event name on the wire is the class name (`"OrderShipped"`) unless you set `name = "custom.name"` on the class.

## Emitting an event

Call `.emit()` on an event instance — it dispatches to all channels in `broadcast_on()`:

```python
OrderShipped(order_id=123).emit()
```

For an awaitable dispatch (e.g. inside an async route handler) use the `broadcast` helper directly:

```python
from fastapi_startkit.broadcasting import broadcast

await broadcast(OrderShipped(order_id=123))
```

## Channel types

| Class | Channel name on wire | Auth required |
|-------|----------------------|---------------|
| `Channel("chat")` | `chat` | No — public, open to all |
| `PrivateChannel("orders.1")` | `private-orders.1` | Yes — checked via `@channel` callback |
| `PresenceChannel("room.1")` | `presence-room.1` | Yes — checked + member tracking |

`PrivateChannel` and `PresenceChannel` automatically prepend `private-` / `presence-` to the name you supply.

## Channel authorization

Private and presence channels require a server-side authorization callback. Register callbacks in `routes/channels.py` using the `@channel` decorator:

```python
# routes/channels.py
from fastapi_startkit.broadcasting import channel

@channel("orders.{order_id}")
async def authorize_orders(user, order_id: int) -> bool:
    """Grant access only to the user who owns the order."""
    return user is not None and user.id == order_id

@channel("private-notifications")
async def authorize_notifications(user) -> bool:
    return user is not None
```

- The pattern supports `{wildcard}` placeholders. Wildcard values are cast to the declared parameter type (e.g. `order_id: int`).
- `user` is the authenticated user injected from the container's auth service.
- Return `True` to grant access, `False` to deny.
- Private/presence channels with **no registered callback are denied by default** (fail-safe).
- `routes/channels.py` is auto-loaded by `ReverbProvider` on boot.

## Registering the provider

Add `ReverbProvider` to your application's providers list:

```python
from fastapi_startkit.broadcasting import ReverbProvider

app = Application(
    providers=[
        ...,
        ReverbProvider,
    ]
)
```

`ReverbProvider` binds `BroadcastManager` into the container, mounts the Reverb WebSocket endpoint, and registers the `/broadcasting/auth` HTTP route used by Laravel Echo for channel handshakes.

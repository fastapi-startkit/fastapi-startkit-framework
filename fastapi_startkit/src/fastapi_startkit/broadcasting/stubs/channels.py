"""Channel authorization callbacks.

Register authorization callbacks for private and presence channels here
using the ``@channel()`` decorator.

Example::

    from fastapi_startkit.broadcasting import channel

    @channel("orders.{order_id}")
    async def authorize_orders_channel(user, order_id: int) -> bool:
        # Return True to grant access, False to deny.
        # `user` is the currently-authenticated user (resolved from the
        # container's `auth` service or request.state.user).
        return user is not None and user.id == order_id

    @channel("private-notifications")
    async def authorize_notifications(user) -> bool:
        return user is not None

Supported channel types:
  - ``Channel("name")``          — public, no auth required
  - ``PrivateChannel("name")``   — auth checked via @channel
  - ``PresenceChannel("name")``  — auth checked + member tracking (v2)

This file is auto-loaded by ReverbProvider when it boots.
"""

from fastapi_startkit.broadcasting import channel  # noqa: F401

# Define your channel authorization callbacks below:
#
# @channel("private-{channel}")
# async def authorize_private_channel(user, channel: str) -> bool:
#     return user is not None

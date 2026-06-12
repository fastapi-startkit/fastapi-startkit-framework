"""Channel authorization callbacks.

Register authorization callbacks for private and presence channels here
using the ``@Broadcast.channel()`` decorator.

Example::

    from fastapi_startkit.facades.Broadcast import Broadcast

    @Broadcast.channel("orders.{order_id}")
    async def authorize_orders_channel(user, order_id: int) -> bool:
        # Return True to grant access, False to deny.
        # `user` is the currently-authenticated user (resolved from the
        # container's ``auth`` service or ``request.state.user``).
        return user is not None and user.id == order_id

    @Broadcast.channel("private-notifications")
    async def authorize_notifications(user) -> bool:
        return user is not None

Supported channel types:
  - ``Channel("name")``          — public, no auth required
  - ``PrivateChannel("name")``   — auth checked via @Broadcast.channel
  - ``PresenceChannel("name")``  — auth checked + member tracking

This file is auto-loaded by ``ReverbProvider`` when it boots.
"""

from fastapi_startkit.facades.Broadcast import Broadcast  # noqa: F401

# Define your channel authorization callbacks below:
#
# @Broadcast.channel("orders.{order_id}")
# async def authorize_orders_channel(user, order_id: int) -> bool:
#     """Authorize the private 'orders.{order_id}' channel.
#
#     Parameters are extracted from the channel name and type-coerced using
#     the type hints on this function.  Return True to allow subscription,
#     False (or raise) to deny.
#     """
#     return user is not None and user.id == order_id

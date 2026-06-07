from fastapi_startkit.broadcasting.channels import Channel, PrivateChannel, PresenceChannel


def test_channel_stores_name():
    ch = Channel("orders.1")
    assert ch.name == "orders.1"


def test_channel_repr():
    ch = Channel("orders.1")
    assert repr(ch) == "Channel('orders.1')"


def test_private_channel_prefixes_name():
    ch = PrivateChannel("orders.1")
    assert ch.name == "private-orders.1"


def test_private_channel_is_channel():
    ch = PrivateChannel("orders.1")
    assert isinstance(ch, Channel)


def test_presence_channel_prefixes_name():
    ch = PresenceChannel("room.42")
    assert ch.name == "presence-room.42"


def test_presence_channel_is_channel():
    ch = PresenceChannel("room.42")
    assert isinstance(ch, Channel)


def test_channel_name_unchanged_for_base():
    ch = Channel("already-prefixed")
    assert ch.name == "already-prefixed"

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


# ---------------------------------------------------------------------------
# __eq__ and __hash__
# ---------------------------------------------------------------------------


def test_channel_equality_same_name():
    assert Channel("orders.1") == Channel("orders.1")


def test_channel_inequality_different_name():
    assert Channel("orders.1") != Channel("orders.2")


def test_channel_equality_not_implemented_for_non_channel():
    ch = Channel("orders.1")
    assert ch.__eq__("orders.1") is NotImplemented


def test_channel_hashable():
    ch = Channel("orders.1")
    assert isinstance(hash(ch), int)


def test_channel_usable_in_set():
    channels = {Channel("orders.1"), Channel("orders.1"), Channel("orders.2")}
    assert len(channels) == 2


def test_channel_usable_as_dict_key():
    d = {Channel("orders.1"): "value"}
    assert d[Channel("orders.1")] == "value"


def test_private_channel_equality():
    assert PrivateChannel("orders") == PrivateChannel("orders")


def test_private_and_base_channel_not_equal():
    # PrivateChannel("orders").name == "private-orders"
    # Channel("orders").name      == "orders"
    assert PrivateChannel("orders") != Channel("orders")

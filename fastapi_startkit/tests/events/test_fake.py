import pytest

from fastapi_startkit.events import Dispatcher, EventFake


class UserRegistered:
    def __init__(self, name: str):
        self.name = name


class OrderShipped:
    def __init__(self, order_id: int):
        self.order_id = order_id


def make_fake(events_to_fake=None):
    return EventFake(Dispatcher(), events_to_fake)


async def test_faked_event_is_not_dispatched_to_listeners():
    dispatcher = Dispatcher()
    called = []
    dispatcher.listen(UserRegistered, lambda e: called.append(e.name))
    fake = dispatcher.fake()

    await fake.dispatch(UserRegistered("ada"))

    assert called == []


async def test_assert_dispatched_passes_when_dispatched():
    fake = make_fake()
    await fake.dispatch(UserRegistered("ada"))

    fake.assert_dispatched(UserRegistered)


async def test_assert_dispatched_fails_when_not_dispatched():
    fake = make_fake()
    with pytest.raises(AssertionError):
        fake.assert_dispatched(UserRegistered)


async def test_assert_dispatched_with_callback():
    fake = make_fake()
    await fake.dispatch(UserRegistered("ada"))

    fake.assert_dispatched(UserRegistered, lambda e: e.name == "ada")
    with pytest.raises(AssertionError):
        fake.assert_dispatched(UserRegistered, lambda e: e.name == "other")


async def test_assert_dispatched_times():
    fake = make_fake()
    await fake.dispatch(UserRegistered("a"))
    await fake.dispatch(UserRegistered("b"))

    fake.assert_dispatched_times(UserRegistered, 2)
    with pytest.raises(AssertionError):
        fake.assert_dispatched_times(UserRegistered, 1)


async def test_assert_not_dispatched():
    fake = make_fake()
    fake.assert_not_dispatched(UserRegistered)

    await fake.dispatch(UserRegistered("a"))
    with pytest.raises(AssertionError):
        fake.assert_not_dispatched(UserRegistered)


async def test_assert_nothing_dispatched():
    fake = make_fake()
    fake.assert_nothing_dispatched()

    await fake.dispatch(UserRegistered("a"))
    with pytest.raises(AssertionError):
        fake.assert_nothing_dispatched()


async def test_dispatched_returns_recorded_events():
    fake = make_fake()
    await fake.dispatch(UserRegistered("a"))
    await fake.dispatch(UserRegistered("b"))

    records = fake.dispatched(UserRegistered)
    assert [e.name for e in records] == ["a", "b"]


async def test_partial_fake_forwards_unfaked_events():
    dispatcher = Dispatcher()
    shipped = []
    dispatcher.listen(OrderShipped, lambda e: shipped.append(e.order_id))
    fake = EventFake(dispatcher, [UserRegistered])

    await fake.dispatch(UserRegistered("ada"))
    await fake.dispatch(OrderShipped(7))

    fake.assert_dispatched(UserRegistered)
    fake.assert_not_dispatched(OrderShipped)
    assert shipped == [7]


async def test_string_event_records_payload():
    fake = make_fake()
    await fake.dispatch("user.registered", ["ada", "pro"])

    fake.assert_dispatched("user.registered")
    assert fake.dispatched("user.registered") == [["ada", "pro"]]


async def test_until_records_faked_event():
    fake = make_fake()
    result = await fake.until(UserRegistered("ada"))

    assert result is None
    fake.assert_dispatched(UserRegistered)


def test_listen_and_has_listeners_pass_through_to_real_dispatcher():
    dispatcher = Dispatcher()
    fake = EventFake(dispatcher)

    fake.listen(UserRegistered, lambda e: None)

    assert fake.has_listeners(UserRegistered) is True
    assert dispatcher.has_listeners(UserRegistered) is True

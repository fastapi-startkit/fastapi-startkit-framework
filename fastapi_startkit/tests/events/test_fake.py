import unittest

from fastapi_startkit.events import Dispatcher, EventFake


class UserRegistered:
    def __init__(self, name: str):
        self.name = name


class OrderShipped:
    def __init__(self, order_id: int):
        self.order_id = order_id


def make_fake(events_to_fake=None):
    return EventFake(Dispatcher(), events_to_fake)


class EventFakeTest(unittest.IsolatedAsyncioTestCase):
    async def test_faked_event_is_not_dispatched_to_listeners(self):
        dispatcher = Dispatcher()
        called = []
        dispatcher.listen(UserRegistered, lambda e: called.append(e.name))
        fake = dispatcher.fake()

        await fake.dispatch(UserRegistered("ada"))

        self.assertEqual(called, [])

    async def test_assert_dispatched_passes_when_dispatched(self):
        fake = make_fake()
        await fake.dispatch(UserRegistered("ada"))

        fake.assert_dispatched(UserRegistered)

    async def test_assert_dispatched_fails_when_not_dispatched(self):
        fake = make_fake()
        with self.assertRaises(AssertionError):
            fake.assert_dispatched(UserRegistered)

    async def test_assert_dispatched_with_callback(self):
        fake = make_fake()
        await fake.dispatch(UserRegistered("ada"))

        fake.assert_dispatched(UserRegistered, lambda e: e.name == "ada")
        with self.assertRaises(AssertionError):
            fake.assert_dispatched(UserRegistered, lambda e: e.name == "other")

    async def test_assert_dispatched_times(self):
        fake = make_fake()
        await fake.dispatch(UserRegistered("a"))
        await fake.dispatch(UserRegistered("b"))

        fake.assert_dispatched_times(UserRegistered, 2)
        with self.assertRaises(AssertionError):
            fake.assert_dispatched_times(UserRegistered, 1)

    async def test_assert_not_dispatched(self):
        fake = make_fake()
        fake.assert_not_dispatched(UserRegistered)

        await fake.dispatch(UserRegistered("a"))
        with self.assertRaises(AssertionError):
            fake.assert_not_dispatched(UserRegistered)

    async def test_assert_nothing_dispatched(self):
        fake = make_fake()
        fake.assert_nothing_dispatched()

        await fake.dispatch(UserRegistered("a"))
        with self.assertRaises(AssertionError):
            fake.assert_nothing_dispatched()

    async def test_dispatched_returns_recorded_events(self):
        fake = make_fake()
        await fake.dispatch(UserRegistered("a"))
        await fake.dispatch(UserRegistered("b"))

        records = fake.dispatched(UserRegistered)
        self.assertEqual([e.name for e in records], ["a", "b"])

    async def test_partial_fake_forwards_unfaked_events(self):
        dispatcher = Dispatcher()
        shipped = []
        dispatcher.listen(OrderShipped, lambda e: shipped.append(e.order_id))
        fake = EventFake(dispatcher, [UserRegistered])

        await fake.dispatch(UserRegistered("ada"))
        await fake.dispatch(OrderShipped(7))

        fake.assert_dispatched(UserRegistered)
        fake.assert_not_dispatched(OrderShipped)
        self.assertEqual(shipped, [7])

    async def test_string_event_records_payload(self):
        fake = make_fake()
        await fake.dispatch("user.registered", ["ada", "pro"])

        fake.assert_dispatched("user.registered")
        self.assertEqual(fake.dispatched("user.registered"), [["ada", "pro"]])

    async def test_until_records_faked_event(self):
        fake = make_fake()
        result = await fake.until(UserRegistered("ada"))

        self.assertIsNone(result)
        fake.assert_dispatched(UserRegistered)

    def test_listen_and_has_listeners_pass_through_to_real_dispatcher(self):
        dispatcher = Dispatcher()
        fake = EventFake(dispatcher)

        fake.listen(UserRegistered, lambda e: None)

        self.assertTrue(fake.has_listeners(UserRegistered))
        self.assertTrue(dispatcher.has_listeners(UserRegistered))

    def test_forget_and_flush_pass_through_to_real_dispatcher(self):
        dispatcher = Dispatcher()
        fake = EventFake(dispatcher)
        fake.listen(UserRegistered, lambda e: None)
        fake.listen(OrderShipped, lambda e: None)

        fake.forget(UserRegistered)
        self.assertFalse(fake.has_listeners(UserRegistered))
        self.assertTrue(fake.has_listeners(OrderShipped))

        fake.flush()
        self.assertFalse(fake.has_listeners(OrderShipped))

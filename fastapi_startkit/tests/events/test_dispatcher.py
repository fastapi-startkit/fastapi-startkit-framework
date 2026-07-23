import unittest

from fastapi_startkit.events import Dispatcher, Listener


class UserRegistered:
    def __init__(self, name: str):
        self.name = name


class OrderShipped:
    def __init__(self, order_id: int):
        self.order_id = order_id


class DispatcherTest(unittest.IsolatedAsyncioTestCase):
    async def test_sync_listener_receives_event(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen(UserRegistered, lambda event: seen.append(event.name))

        await dispatcher.dispatch(UserRegistered("ada"))

        self.assertEqual(seen, ["ada"])

    async def test_async_listener_is_awaited(self):
        dispatcher = Dispatcher()
        seen = []

        async def listener(event):
            seen.append(event.name)

        dispatcher.listen(UserRegistered, listener)
        await dispatcher.dispatch(UserRegistered("lin"))

        self.assertEqual(seen, ["lin"])

    async def test_class_listener_handle_is_called(self):
        dispatcher = Dispatcher()
        calls = []

        class SendWelcomeEmail(Listener):
            def handle(self, event):
                calls.append(event.name)

        dispatcher.listen(UserRegistered, SendWelcomeEmail)
        await dispatcher.dispatch(UserRegistered("grace"))

        self.assertEqual(calls, ["grace"])

    async def test_class_listener_with_async_handle(self):
        dispatcher = Dispatcher()
        calls = []

        class SendWelcomeEmail:
            async def handle(self, event):
                calls.append(event.name)

        dispatcher.listen(UserRegistered, SendWelcomeEmail)
        await dispatcher.dispatch(UserRegistered("hopper"))

        self.assertEqual(calls, ["hopper"])

    async def test_multiple_listeners_fire_in_registration_order(self):
        dispatcher = Dispatcher()
        order = []
        dispatcher.listen(UserRegistered, lambda e: order.append("first"))
        dispatcher.listen(UserRegistered, lambda e: order.append("second"))

        await dispatcher.dispatch(UserRegistered("x"))

        self.assertEqual(order, ["first", "second"])

    async def test_dispatch_returns_listener_responses(self):
        dispatcher = Dispatcher()
        dispatcher.listen(UserRegistered, lambda e: "a")
        dispatcher.listen(UserRegistered, lambda e: "b")

        responses = await dispatcher.dispatch(UserRegistered("x"))

        self.assertEqual(responses, ["a", "b"])

    async def test_returning_false_stops_propagation(self):
        dispatcher = Dispatcher()
        order = []
        dispatcher.listen(UserRegistered, lambda e: order.append("first") or False)
        dispatcher.listen(UserRegistered, lambda e: order.append("second"))

        await dispatcher.dispatch(UserRegistered("x"))

        self.assertEqual(order, ["first"])

    async def test_until_returns_first_non_none_response(self):
        dispatcher = Dispatcher()
        dispatcher.listen(UserRegistered, lambda e: None)
        dispatcher.listen(UserRegistered, lambda e: "handled")
        dispatcher.listen(UserRegistered, lambda e: "ignored")

        result = await dispatcher.until(UserRegistered("x"))

        self.assertEqual(result, "handled")

    async def test_string_event_with_payload_list_is_spread(self):
        dispatcher = Dispatcher()
        captured = []
        dispatcher.listen("user.registered", lambda name, plan: captured.append((name, plan)))

        await dispatcher.dispatch("user.registered", ["ada", "pro"])

        self.assertEqual(captured, [("ada", "pro")])

    async def test_string_event_with_no_payload(self):
        dispatcher = Dispatcher()
        calls = []
        dispatcher.listen("cache.flushed", lambda: calls.append(True))

        await dispatcher.dispatch("cache.flushed")

        self.assertEqual(calls, [True])

    async def test_string_event_with_scalar_payload(self):
        dispatcher = Dispatcher()
        captured = []
        dispatcher.listen("cache.cleared", lambda key: captured.append(key))

        await dispatcher.dispatch("cache.cleared", "users")

        self.assertEqual(captured, ["users"])

    async def test_listen_accepts_a_list_of_events(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen([UserRegistered, OrderShipped], lambda e: seen.append(type(e).__name__))

        await dispatcher.dispatch(UserRegistered("x"))
        await dispatcher.dispatch(OrderShipped(1))

        self.assertEqual(seen, ["UserRegistered", "OrderShipped"])

    async def test_listen_as_decorator(self):
        dispatcher = Dispatcher()
        seen = []

        @dispatcher.listen(UserRegistered)
        def handler(event):
            seen.append(event.name)

        await dispatcher.dispatch(UserRegistered("curie"))

        self.assertEqual(seen, ["curie"])
        self.assertTrue(callable(handler))

    async def test_wildcard_listener_fires_on_matching_event(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen("user.*", lambda: seen.append(True))

        await dispatcher.dispatch("user.created")

        self.assertEqual(seen, [True])

    async def test_wildcard_listener_does_not_fire_on_non_matching_event(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen("user.*", lambda: seen.append(True))

        await dispatcher.dispatch("order.created")

        self.assertEqual(seen, [])

    async def test_wildcard_receives_event_payload(self):
        dispatcher = Dispatcher()
        captured = []
        dispatcher.listen("user.*", lambda name: captured.append(name))

        await dispatcher.dispatch("user.created", "ada")

        self.assertEqual(captured, ["ada"])

    async def test_multiple_wildcard_patterns_each_match_independently(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen("user.*", lambda: seen.append("user"))
        dispatcher.listen("*.created", lambda: seen.append("created"))
        dispatcher.listen("order.*", lambda: seen.append("order"))

        await dispatcher.dispatch("user.created")

        self.assertEqual(sorted(seen), ["created", "user"])

    async def test_wildcard_and_exact_listeners_both_fire_exact_first(self):
        dispatcher = Dispatcher()
        order = []
        dispatcher.listen("user.*", lambda: order.append("wildcard"))
        dispatcher.listen("user.created", lambda: order.append("exact"))

        await dispatcher.dispatch("user.created")

        self.assertEqual(order, ["exact", "wildcard"])

    async def test_wildcard_matches_across_multiple_segments(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen("user.*", lambda: seen.append(True))

        await dispatcher.dispatch("user.profile.updated")

        self.assertEqual(seen, [True])

    async def test_until_halts_across_exact_and_wildcard(self):
        dispatcher = Dispatcher()
        dispatcher.listen("user.created", lambda: None)
        dispatcher.listen("user.*", lambda: "handled")

        result = await dispatcher.until("user.created")

        self.assertEqual(result, "handled")

    def test_has_listeners_true_for_wildcard_match(self):
        dispatcher = Dispatcher()
        dispatcher.listen("user.*", lambda: None)

        self.assertTrue(dispatcher.has_listeners("user.created"))
        self.assertFalse(dispatcher.has_listeners("order.created"))

    def test_has_listeners(self):
        dispatcher = Dispatcher()
        self.assertFalse(dispatcher.has_listeners(UserRegistered))
        dispatcher.listen(UserRegistered, lambda e: None)
        self.assertTrue(dispatcher.has_listeners(UserRegistered))

    async def test_forget_removes_listeners(self):
        dispatcher = Dispatcher()
        seen = []
        dispatcher.listen(UserRegistered, lambda e: seen.append(1))
        dispatcher.forget(UserRegistered)

        await dispatcher.dispatch(UserRegistered("x"))

        self.assertEqual(seen, [])
        self.assertFalse(dispatcher.has_listeners(UserRegistered))

    async def test_flush_removes_all_listeners(self):
        dispatcher = Dispatcher()
        dispatcher.listen(UserRegistered, lambda e: None)
        dispatcher.listen(OrderShipped, lambda e: None)

        dispatcher.flush()

        self.assertFalse(dispatcher.has_listeners(UserRegistered))
        self.assertFalse(dispatcher.has_listeners(OrderShipped))

    async def test_dispatch_with_no_listeners_returns_empty_list(self):
        dispatcher = Dispatcher()
        self.assertEqual(await dispatcher.dispatch(UserRegistered("x")), [])

    async def test_listener_class_dependencies_resolved_by_container(self):
        from fastapi_startkit.container import Container

        class Mailer:
            def __init__(self):
                self.sent = []

        container = Container()
        mailer = Mailer()
        container.bind("mailer", mailer)

        class SendWelcomeEmail:
            def __init__(self, mailer: Mailer):
                self.mailer = mailer

            def handle(self, event):
                self.mailer.sent.append(event.name)

        dispatcher = Dispatcher(container)
        dispatcher.listen(UserRegistered, SendWelcomeEmail)

        await dispatcher.dispatch(UserRegistered("noether"))

        self.assertEqual(mailer.sent, ["noether"])


class ListenerTest(unittest.TestCase):
    def test_listener_abc_requires_handle(self):
        with self.assertRaises(TypeError):
            Listener()  # type: ignore[abstract]

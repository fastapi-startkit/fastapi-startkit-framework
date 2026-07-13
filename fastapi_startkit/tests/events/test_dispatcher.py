import pytest

from fastapi_startkit.events import Dispatcher, Listener


class UserRegistered:
    def __init__(self, name: str):
        self.name = name


class OrderShipped:
    def __init__(self, order_id: int):
        self.order_id = order_id


async def test_sync_listener_receives_event():
    dispatcher = Dispatcher()
    seen = []
    dispatcher.listen(UserRegistered, lambda event: seen.append(event.name))

    await dispatcher.dispatch(UserRegistered("ada"))

    assert seen == ["ada"]


async def test_async_listener_is_awaited():
    dispatcher = Dispatcher()
    seen = []

    async def listener(event):
        seen.append(event.name)

    dispatcher.listen(UserRegistered, listener)
    await dispatcher.dispatch(UserRegistered("lin"))

    assert seen == ["lin"]


async def test_class_listener_handle_is_called():
    dispatcher = Dispatcher()
    calls = []

    class SendWelcomeEmail(Listener):
        def handle(self, event):
            calls.append(event.name)

    dispatcher.listen(UserRegistered, SendWelcomeEmail)
    await dispatcher.dispatch(UserRegistered("grace"))

    assert calls == ["grace"]


async def test_class_listener_with_async_handle():
    dispatcher = Dispatcher()
    calls = []

    class SendWelcomeEmail:
        async def handle(self, event):
            calls.append(event.name)

    dispatcher.listen(UserRegistered, SendWelcomeEmail)
    await dispatcher.dispatch(UserRegistered("hopper"))

    assert calls == ["hopper"]


async def test_multiple_listeners_fire_in_registration_order():
    dispatcher = Dispatcher()
    order = []
    dispatcher.listen(UserRegistered, lambda e: order.append("first"))
    dispatcher.listen(UserRegistered, lambda e: order.append("second"))

    await dispatcher.dispatch(UserRegistered("x"))

    assert order == ["first", "second"]


async def test_dispatch_returns_listener_responses():
    dispatcher = Dispatcher()
    dispatcher.listen(UserRegistered, lambda e: "a")
    dispatcher.listen(UserRegistered, lambda e: "b")

    responses = await dispatcher.dispatch(UserRegistered("x"))

    assert responses == ["a", "b"]


async def test_returning_false_stops_propagation():
    dispatcher = Dispatcher()
    order = []
    dispatcher.listen(UserRegistered, lambda e: order.append("first") or False)
    dispatcher.listen(UserRegistered, lambda e: order.append("second"))

    await dispatcher.dispatch(UserRegistered("x"))

    assert order == ["first"]


async def test_until_returns_first_non_none_response():
    dispatcher = Dispatcher()
    dispatcher.listen(UserRegistered, lambda e: None)
    dispatcher.listen(UserRegistered, lambda e: "handled")
    dispatcher.listen(UserRegistered, lambda e: "ignored")

    result = await dispatcher.until(UserRegistered("x"))

    assert result == "handled"


async def test_string_event_with_payload_list_is_spread():
    dispatcher = Dispatcher()
    captured = []
    dispatcher.listen("user.registered", lambda name, plan: captured.append((name, plan)))

    await dispatcher.dispatch("user.registered", ["ada", "pro"])

    assert captured == [("ada", "pro")]


async def test_string_event_with_no_payload():
    dispatcher = Dispatcher()
    calls = []
    dispatcher.listen("cache.flushed", lambda: calls.append(True))

    await dispatcher.dispatch("cache.flushed")

    assert calls == [True]


async def test_string_event_with_scalar_payload():
    dispatcher = Dispatcher()
    captured = []
    dispatcher.listen("cache.cleared", lambda key: captured.append(key))

    await dispatcher.dispatch("cache.cleared", "users")

    assert captured == ["users"]


async def test_listen_accepts_a_list_of_events():
    dispatcher = Dispatcher()
    seen = []
    dispatcher.listen([UserRegistered, OrderShipped], lambda e: seen.append(type(e).__name__))

    await dispatcher.dispatch(UserRegistered("x"))
    await dispatcher.dispatch(OrderShipped(1))

    assert seen == ["UserRegistered", "OrderShipped"]


async def test_listen_as_decorator():
    dispatcher = Dispatcher()
    seen = []

    @dispatcher.listen(UserRegistered)
    def handler(event):
        seen.append(event.name)

    await dispatcher.dispatch(UserRegistered("curie"))

    assert seen == ["curie"]
    assert callable(handler)


def test_has_listeners():
    dispatcher = Dispatcher()
    assert dispatcher.has_listeners(UserRegistered) is False
    dispatcher.listen(UserRegistered, lambda e: None)
    assert dispatcher.has_listeners(UserRegistered) is True


async def test_forget_removes_listeners():
    dispatcher = Dispatcher()
    seen = []
    dispatcher.listen(UserRegistered, lambda e: seen.append(1))
    dispatcher.forget(UserRegistered)

    await dispatcher.dispatch(UserRegistered("x"))

    assert seen == []
    assert dispatcher.has_listeners(UserRegistered) is False


async def test_flush_removes_all_listeners():
    dispatcher = Dispatcher()
    dispatcher.listen(UserRegistered, lambda e: None)
    dispatcher.listen(OrderShipped, lambda e: None)

    dispatcher.flush()

    assert dispatcher.has_listeners(UserRegistered) is False
    assert dispatcher.has_listeners(OrderShipped) is False


async def test_dispatch_with_no_listeners_returns_empty_list():
    dispatcher = Dispatcher()
    assert await dispatcher.dispatch(UserRegistered("x")) == []


async def test_listener_class_dependencies_resolved_by_container():
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

    assert mailer.sent == ["noether"]


def test_listener_abc_requires_handle():
    with pytest.raises(TypeError):
        Listener()  # type: ignore[abstract]

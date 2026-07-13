import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.events import Dispatcher, EventServiceProvider


class UserRegistered:
    def __init__(self, name: str):
        self.name = name


received = []


class RecordRegistration:
    def handle(self, event):
        received.append(event.name)


class AppEventServiceProvider(EventServiceProvider):
    listen = {
        UserRegistered: [RecordRegistration],
    }


@pytest.fixture(autouse=True)
def restore_container_instance():
    original = Container._instance
    received.clear()
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing", providers=[AppEventServiceProvider])


def test_dispatcher_is_bound_by_default(tmp_path):
    app = Application(base_path=tmp_path, env="testing")
    assert app.has("events")
    assert isinstance(app.make("events"), Dispatcher)


async def test_provider_wires_listen_map(app):
    await app.make("events").dispatch(UserRegistered("ada"))
    assert received == ["ada"]


async def test_event_facade_dispatches(app):
    from fastapi_startkit.facades import Event

    seen = []
    Event.listen(UserRegistered, lambda e: seen.append(e.name))
    await Event.dispatch(UserRegistered("lin"))

    assert seen == ["lin"]


async def test_event_helper_dispatches(app):
    from fastapi_startkit.events import event

    seen = []
    app.make("events").listen(UserRegistered, lambda e: seen.append(e.name))
    await event(UserRegistered("grace"))

    assert seen == ["grace"]


async def test_event_facade_fake_records_without_calling_listeners(app):
    from fastapi_startkit.facades import Event

    called = []
    Event.listen(UserRegistered, lambda e: called.append(e.name))

    fake = Event.fake()
    await Event.dispatch(UserRegistered("noether"))

    assert called == []
    fake.assert_dispatched(UserRegistered)

import tempfile
import unittest
from pathlib import Path

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


class EventServiceProviderTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.base_path = Path(self._tmp_dir.name)

        self._original_container_instance = Container._instance
        received.clear()

    def tearDown(self):
        Container._instance = self._original_container_instance

    def _make_app(self):
        return Application(base_path=self.base_path, env="testing", providers=[AppEventServiceProvider])

    def test_dispatcher_is_bound_by_default(self):
        app = Application(base_path=self.base_path, env="testing")
        self.assertTrue(app.has("events"))
        self.assertIsInstance(app.make("events"), Dispatcher)

    async def test_provider_wires_listen_map(self):
        app = self._make_app()
        await app.make("events").dispatch(UserRegistered("ada"))
        self.assertEqual(received, ["ada"])

    async def test_event_facade_dispatches(self):
        self._make_app()
        from fastapi_startkit.facades import Event

        seen = []
        Event.listen(UserRegistered, lambda e: seen.append(e.name))
        await Event.dispatch(UserRegistered("lin"))

        self.assertEqual(seen, ["lin"])

    async def test_event_helper_dispatches(self):
        app = self._make_app()
        from fastapi_startkit.events import event

        seen = []
        app.make("events").listen(UserRegistered, lambda e: seen.append(e.name))
        await event(UserRegistered("grace"))

        self.assertEqual(seen, ["grace"])

    async def test_event_facade_fake_records_without_calling_listeners(self):
        self._make_app()
        from fastapi_startkit.facades import Event

        called = []
        Event.listen(UserRegistered, lambda e: called.append(e.name))

        fake = Event.fake()
        await Event.dispatch(UserRegistered("noether"))

        self.assertEqual(called, [])
        fake.assert_dispatched(UserRegistered)

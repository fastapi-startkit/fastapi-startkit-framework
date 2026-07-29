"""Tests for RequestLifecycleMiddleware — structured RequestHandled events (task #1324)."""

import tempfile
import unittest
from pathlib import Path

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.facades import Event
from fastapi_startkit.fastapi import FastAPIProvider, RequestHandled
from fastapi_startkit.fastapi.middleware import REQUEST_ID_HEADER


def make_client(app: Application) -> TestClient:
    @app.fastapi.get("/ping")
    def ping():
        return {"ok": True}

    @app.fastapi.get("/boom")
    def boom():
        return JSONResponse(status_code=404, content={"detail": "not found"})

    return TestClient(app.fastapi)


class RequestLifecycleEventTest(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self._original_container_instance = Container._instance
        self.addCleanup(self._restore_container)

        self.app = Application(base_path=Path(self._tmp_dir.name), env="testing", providers=[FastAPIProvider])
        self.client = make_client(self.app)

    def _restore_container(self):
        Container._instance = self._original_container_instance

    def test_dispatches_request_handled_event(self):
        seen = []
        Event.listen(RequestHandled, lambda e: seen.append(e))

        response = self.client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(seen), 1)
        event = seen[0]
        self.assertEqual(event.method, "GET")
        self.assertEqual(event.path, "/ping")
        self.assertEqual(event.status_code, 200)
        self.assertGreaterEqual(event.duration_ms, 0)
        self.assertTrue(event.request_id)

    def test_event_reflects_error_status_code(self):
        seen = []
        Event.listen(RequestHandled, lambda e: seen.append(e))

        response = self.client.get("/boom")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(seen[0].status_code, 404)

    def test_response_carries_generated_request_id_header(self):
        response = self.client.get("/ping")

        self.assertIn(REQUEST_ID_HEADER, response.headers)
        self.assertTrue(response.headers[REQUEST_ID_HEADER])

    def test_incoming_request_id_is_echoed_back(self):
        response = self.client.get("/ping", headers={REQUEST_ID_HEADER: "client-supplied-id"})

        self.assertEqual(response.headers[REQUEST_ID_HEADER], "client-supplied-id")

        seen = []
        Event.listen(RequestHandled, lambda e: seen.append(e))
        self.client.get("/ping", headers={REQUEST_ID_HEADER: "another-id"})
        self.assertEqual(seen[0].request_id, "another-id")

    def test_event_fake_records_without_invoking_real_listener(self):
        called = []
        Event.listen(RequestHandled, lambda e: called.append(e))

        fake = Event.fake()
        self.client.get("/ping")

        self.assertEqual(called, [])
        fake.assert_dispatched(RequestHandled, lambda e: e.path == "/ping" and e.status_code == 200)

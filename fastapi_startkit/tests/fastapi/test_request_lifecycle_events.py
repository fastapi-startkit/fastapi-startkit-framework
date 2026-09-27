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

    @app.fastapi.get("/crash")
    def crash():
        raise RuntimeError("bare exception escaping the route")

    return TestClient(app.fastapi, raise_server_exceptions=False)


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

    # -----------------------------------------------------------------
    # Bare exception escaping the route (task #1329 regression)
    # -----------------------------------------------------------------
    #
    # A bare (non-HTTPException) exception is handled by Starlette's
    # ServerErrorMiddleware, which sits *outside* RequestLifecycleMiddleware —
    # unlike HTTPException, which stays inside it via ExceptionMiddleware.
    # The event must still log status_code=500, and the response the client
    # actually receives must still carry the same X-Request-Id.

    def test_event_reflects_bare_exception_as_500(self):
        seen = []
        Event.listen(RequestHandled, lambda e: seen.append(e))

        response = self.client.get("/crash")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(seen[0].status_code, 500)

    def test_response_carries_request_id_when_bare_exception_escapes(self):
        response = self.client.get("/crash")

        self.assertIn(REQUEST_ID_HEADER, response.headers)
        self.assertTrue(response.headers[REQUEST_ID_HEADER])

    def test_response_request_id_matches_event_request_id_on_crash(self):
        seen = []
        Event.listen(RequestHandled, lambda e: seen.append(e))

        response = self.client.get("/crash")

        self.assertEqual(response.headers[REQUEST_ID_HEADER], seen[0].request_id)

    def test_incoming_request_id_is_echoed_back_on_crash(self):
        response = self.client.get("/crash", headers={REQUEST_ID_HEADER: "crash-request-id"})

        self.assertEqual(response.headers[REQUEST_ID_HEADER], "crash-request-id")

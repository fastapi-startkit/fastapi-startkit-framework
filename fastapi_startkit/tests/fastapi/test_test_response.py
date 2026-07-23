"""Unit tests for the TestResponse httpx wrapper + fluent assert_json."""

import json as jsonlib
import unittest

import httpx

from fastapi_startkit.fastapi.testing.test_response import TestResponse


def make_response(status_code=200, payload=None):
    content = jsonlib.dumps(payload if payload is not None else {})
    raw = httpx.Response(
        status_code=status_code,
        content=content.encode(),
        headers={"content-type": "application/json"},
    )
    return TestResponse(raw)


def make_sse_response(*chunks, status_code=200):
    body = "".join(f"data: {chunk}\n\n" for chunk in chunks)
    raw = httpx.Response(
        status_code=status_code,
        content=body.encode(),
        headers={"content-type": "text/event-stream"},
    )
    return TestResponse(raw)


class TestTestResponse(unittest.TestCase):
    def test_passthrough_attributes(self):
        resp = make_response(200, {"message": "ok"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"message": "ok"})
        self.assertEqual(resp.text, '{"message": "ok"}')

    def test_assert_status_and_ok(self):
        resp = make_response(200, {"a": 1})
        self.assertIs(resp.assert_status(200).assert_ok(), resp)

    def test_assert_status_failure_includes_body(self):
        resp = make_response(500, {"error": "boom"})
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_status(200)
        self.assertIn("boom", str(ctx.exception))

    def test_assert_created_and_no_content(self):
        make_response(201, {}).assert_created()
        make_response(204, {}).assert_no_content()

    def test_assert_json_fluent_chain(self):
        resp = make_response(200, {"id": 1, "name": "Bedu"})
        resp.assert_ok().assert_json(lambda j: j.where("id", 1).where("name", "Bedu").etc())

    def test_assert_json_strict_failure_on_extra_key(self):
        resp = make_response(200, {"id": 1, "secret": "leak"})
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_json(lambda j: j.where("id", 1))
        self.assertIn("secret", str(ctx.exception))

    def test_assert_json_exact(self):
        resp = make_response(200, {"id": 1})
        resp.assert_json(exact={"id": 1})
        with self.assertRaises(AssertionError):
            resp.assert_json(exact={"id": 2})

    def test_assert_json_structure_wildcard(self):
        payload = {"teams": [{"name": "Suns", "sport": "b"}, {"name": "Cardinals", "sport": "f"}]}
        resp = make_response(200, payload)
        resp.assert_ok().assert_json_structure({"teams": {"*": ["name", "sport"]}})

    def test_assert_json_structure_failure(self):
        resp = make_response(200, {"teams": [{"name": "Suns"}]})
        with self.assertRaises(AssertionError):
            resp.assert_json_structure({"teams": {"*": ["name", "sport"]}})

    def test_assert_json_dotted_list_index_scope(self):
        payload = {"teams": [{"name": "Phoenix Suns", "sport": "basketball"}]}
        resp = make_response(200, payload)
        resp.assert_json(
            lambda j: j.has("teams", 1).has("teams.0", lambda team: team.where("name", "Phoenix Suns").etc())
        )

    def test_stream_chunks_decodes_each_sse_event(self):
        resp = make_sse_response("Hello", " there!")
        self.assertEqual(resp.stream_chunks(), ["Hello", " there!"])

    def test_stream_content_concatenates_payloads(self):
        resp = make_sse_response("Hello", " there!")
        self.assertEqual(resp.stream_content(), "Hello there!")

    def test_assert_stream_single_string_matches_joined_content(self):
        resp = make_sse_response("Hello", " there!")
        self.assertIs(resp.assert_ok().assert_stream("Hello there!"), resp)

    def test_assert_stream_multiple_args_match_exact_chunks(self):
        resp = make_sse_response("Hello", " there!")
        resp.assert_stream("Hello", " there!")

    def test_assert_stream_joined_mismatch_raises(self):
        resp = make_sse_response("Hello")
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_stream("Goodbye")
        self.assertIn("Goodbye", str(ctx.exception))

    def test_assert_stream_chunk_sequence_mismatch_raises(self):
        resp = make_sse_response("Hello", " there!")
        with self.assertRaises(AssertionError):
            resp.assert_stream("Hello", " world!")

    def test_stream_chunks_ignores_non_data_lines(self):
        body = "event: message\ndata: only this\nid: 1\n\n"
        raw = httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})
        self.assertEqual(TestResponse(raw).stream_chunks(), ["only this"])

    def test_is_stream_true_for_event_stream_and_false_for_json(self):
        self.assertTrue(make_sse_response("x").is_stream())
        self.assertFalse(make_response(200, {"a": 1}).is_stream())

    def test_assert_stream_raises_on_non_stream_response(self):
        resp = make_response(200, {"content": "Hello there!"})
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_stream("Hello there!")
        self.assertIn("streaming", str(ctx.exception))
        self.assertIn("assert_contents", str(ctx.exception))

    def test_assert_stream_contains_raises_on_non_stream_response(self):
        resp = make_response(200, {"content": "Hello there!"})
        with self.assertRaises(AssertionError):
            resp.assert_stream_contains("Hello")

    def test_assert_stream_contains_matches_substrings(self):
        resp = make_sse_response("Hello ", "Bedram", "!")
        self.assertIs(resp.assert_stream_contains("Bedram", "Hello"), resp)

    def test_assert_stream_contains_mismatch_raises(self):
        resp = make_sse_response("Hello there!")
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_stream_contains("Goodbye")
        self.assertIn("Goodbye", str(ctx.exception))

    def test_assert_contents_matches_buffered_body(self):
        resp = make_response(200, {"content": "Hello Alex, nice to meet you"})
        self.assertIs(resp.assert_contents("Alex", "nice to meet"), resp)

    def test_assert_contents_mismatch_raises(self):
        resp = make_response(200, {"content": "Hello there"})
        with self.assertRaises(AssertionError) as ctx:
            resp.assert_contents("Goodbye")
        self.assertIn("Goodbye", str(ctx.exception))

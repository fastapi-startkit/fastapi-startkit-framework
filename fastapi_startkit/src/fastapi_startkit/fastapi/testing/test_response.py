"""A thin, chainable wrapper around ``httpx.Response`` for HTTP tests.

:class:`TestResponse` adds assertion helpers
(``assert_status``, ``assert_ok``, ``assert_json``) while transparently
delegating every other attribute/method to the underlying ``httpx.Response``
via ``__getattr__``. Existing tests that read ``response.status_code`` or call
``response.json()`` continue to work unchanged.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from httpx import Response

from fastapi_startkit.fastapi.testing.assertable_json import (
    AssertableJson,
    assert_json_structure,
)


class TestResponse:
    """Wraps an ``httpx.Response`` and adds fluent assertion helpers."""

    # Prevent pytest from trying to collect this as a test class.
    __test__ = False

    def __init__(self, response: Response) -> None:
        self._response = response

    @property
    def response(self) -> Response:
        """Access the underlying ``httpx.Response`` directly."""
        return self._response

    def __getattr__(self, name: str) -> Any:
        # Only called when ``name`` is not found on this wrapper, so this
        # transparently forwards status_code, headers, json(), text, etc.
        return getattr(self._response, name)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<TestResponse {self._response.status_code} {self._response.url}>"

    # ------------------------------------------------------------------ #
    # Status assertions
    # ------------------------------------------------------------------ #
    def assert_status(self, code: int) -> "TestResponse":
        """Assert the response has the given HTTP status code."""
        actual = self._response.status_code
        assert actual == code, f"Expected status code [{code}] but received [{actual}]. Body: {self._response.text}"
        return self

    def assert_ok(self) -> "TestResponse":
        """Assert the response status code is 200 OK."""
        return self.assert_status(200)

    def assert_created(self) -> "TestResponse":
        """Assert the response status code is 201 Created."""
        return self.assert_status(201)

    def assert_no_content(self) -> "TestResponse":
        """Assert the response status code is 204 No Content."""
        return self.assert_status(204)

    # ------------------------------------------------------------------ #
    # JSON assertions
    # ------------------------------------------------------------------ #
    def assert_json(
        self,
        callback: Optional[Callable[[AssertableJson], Any]] = None,
        *,
        exact: Any = None,
    ) -> "TestResponse":
        """Assert against the JSON body.

        * ``assert_json(lambda j: j.where(...))`` — run fluent assertions; the
          strict interaction model is enforced (unexpected keys fail unless
          ``etc()`` is called).
        * ``assert_json(exact={...})`` — assert the decoded body equals
          ``exact`` exactly.
        """
        body = self._response.json()
        if callback is not None:
            fluent = AssertableJson(body)
            callback(fluent)
            fluent._verify()
        if exact is not None:
            assert body == exact, f"JSON body does not match exactly.\nExpected: {exact!r}\nActual:   {body!r}"
        return self

    def assert_json_structure(self, structure: Any) -> "TestResponse":
        """Assert the JSON body has the given key structure.

        Use a ``"*"`` key to apply a nested structure to every element of a
        list::

            response.assert_json_structure({
                "teams": {"*": ["name", "sport"]},
            })
        """
        assert_json_structure(structure, self._response.json())
        return self

    # ------------------------------------------------------------------ #
    # Streaming (Server-Sent Events) assertions
    # ------------------------------------------------------------------ #
    def stream_chunks(self) -> list[str]:
        """Return the ``data:`` payloads of a Server-Sent Events body.

        Each ``data:`` line becomes one chunk, with the single optional space
        after the colon removed per the SSE spec.
        """
        chunks: list[str] = []
        for line in self._response.text.splitlines():
            if not line.startswith("data:"):
                continue
            value = line[len("data:") :]
            chunks.append(value[1:] if value.startswith(" ") else value)
        return chunks

    def stream_content(self) -> str:
        """Concatenate the SSE ``data:`` payloads into the full streamed text."""
        return "".join(self.stream_chunks())

    def assert_stream(self, *expected: str) -> "TestResponse":
        """Assert against a streamed (``text/event-stream``) body.

        * ``assert_stream("Hello there!")`` — assert the concatenated stream
          content equals the single expected string.
        * ``assert_stream("Hello", " there!")`` — assert the exact sequence of
          streamed chunks.
        """
        chunks = self.stream_chunks()
        if len(expected) == 1:
            content = "".join(chunks)
            assert content == expected[0], f"Expected streamed content [{expected[0]!r}] but received [{content!r}]."
        else:
            assert chunks == list(expected), f"Expected streamed chunks {list(expected)!r} but received {chunks!r}."
        return self

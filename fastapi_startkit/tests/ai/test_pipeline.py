import unittest

from fastapi_startkit.ai.pipeline import Middleware, Response, build_pipeline


def _stream(*chunks):
    async def _source():
        for chunk in chunks:
            yield chunk

    return _source


class TestResponse(unittest.IsolatedAsyncioTestCase):
    async def test_await_returns_accumulated_value(self):
        result = await Response(_stream("a", "b", "c"))

        self.assertEqual(result, "abc")

    async def test_async_for_yields_each_chunk(self):
        chunks = [chunk async for chunk in Response(_stream("a", "b", "c"))]

        self.assertEqual(chunks, ["a", "b", "c"])

    async def test_then_callback_receives_accumulated_final_on_await(self):
        seen = []
        await Response(_stream("a", "b", "c")).then(seen.append)

        self.assertEqual(seen, ["abc"])

    async def test_then_callback_fires_after_streaming_is_drained(self):
        events = []

        response = Response(_stream("a", "b")).then(lambda final: events.append(("after", final)))
        async for chunk in response:
            events.append(("chunk", chunk))

        self.assertEqual(events, [("chunk", "a"), ("chunk", "b"), ("after", "ab")])

    async def test_then_fires_exactly_once_per_consumption(self):
        calls = []

        await Response(_stream("x", "y")).then(lambda final: calls.append(final))

        self.assertEqual(calls, ["xy"])

    async def test_multiple_callbacks_fire_in_registration_order(self):
        order = []

        response = Response(_stream("z")).then(lambda f: order.append("first")).then(lambda f: order.append("second"))
        await response

        self.assertEqual(order, ["first", "second"])

    async def test_then_returns_self_for_chaining(self):
        response = Response(_stream("a"))

        self.assertIs(response.then(lambda f: None), response)

    async def test_async_callback_is_awaited(self):
        awaited = []

        async def record(final):
            awaited.append(final)

        await Response(_stream("a", "b")).then(record)

        self.assertEqual(awaited, ["ab"])

    async def test_empty_stream_passes_none_to_callback(self):
        seen = []

        await Response(_stream()).then(seen.append)

        self.assertEqual(seen, [None])


class TestBuildPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        async def _core_source(model):
            for token in ("one", " two", " three"):
                yield token

        self.core = lambda model: Response(lambda: _core_source(model))

    async def test_no_middleware_passes_core_through(self):
        pipeline = build_pipeline([], self.core)

        self.assertEqual(await pipeline("m"), "one two three")

    async def test_after_hook_fires_on_buffered_await(self):
        events = []

        class Logger:
            def handle(self, model, handler):
                events.append("request")
                return handler(model).then(lambda final: events.append(("response", final)))

        pipeline = build_pipeline([Logger()], self.core)
        result = await pipeline("m")

        self.assertEqual(result, "one two three")
        self.assertEqual(events, ["request", ("response", "one two three")])

    async def test_after_hook_fires_on_streaming_iteration(self):
        events = []

        class Logger:
            def handle(self, model, handler):
                events.append("request")
                return handler(model).then(lambda final: events.append(("response", final)))

        pipeline = build_pipeline([Logger()], self.core)
        chunks = [chunk async for chunk in pipeline("m")]

        self.assertEqual(chunks, ["one", " two", " three"])
        self.assertEqual(events, ["request", ("response", "one two three")])

    async def test_async_handle_is_supported(self):
        events = []

        class Logger:
            async def handle(self, model, handler):
                events.append("request")
                return handler(model).then(lambda final: events.append("response"))

        pipeline = build_pipeline([Logger()], self.core)
        await pipeline("m")

        self.assertEqual(events, ["request", "response"])

    async def test_middleware_class_is_instantiated(self):
        events = []

        class Logger:
            def handle(self, model, handler):
                events.append("request")
                return handler(model)

        pipeline = build_pipeline([Logger], self.core)
        await pipeline("m")

        self.assertEqual(events, ["request"])

    async def test_onion_order_before_outer_to_inner_after_inner_to_outer(self):
        events = []

        def layer(name):
            class Layer:
                def handle(self, model, handler):
                    events.append(f"before:{name}")
                    return handler(model).then(lambda final: events.append(f"after:{name}"))

            return Layer()

        pipeline = build_pipeline([layer("outer"), layer("inner")], self.core)
        await pipeline("m")

        self.assertEqual(
            events,
            ["before:outer", "before:inner", "after:inner", "after:outer"],
        )

    async def test_middleware_may_short_circuit_with_a_bare_value(self):
        class Canned:
            def handle(self, model, handler):
                return "canned reply"

        pipeline = build_pipeline([Canned()], self.core)

        self.assertEqual(await pipeline("m"), "canned reply")
        self.assertEqual([chunk async for chunk in pipeline("m")], ["canned reply"])

    async def test_middleware_receives_the_model(self):
        seen = []

        class Capture:
            def handle(self, model, handler):
                seen.append(model)
                return handler(model)

        pipeline = build_pipeline([Capture()], self.core)
        await pipeline("gpt-test")

        self.assertEqual(seen, ["gpt-test"])

    async def test_after_hook_runs_once_even_with_multiple_chunks(self):
        calls = []

        class Logger:
            def handle(self, model, handler):
                return handler(model).then(lambda final: calls.append(final))

        pipeline = build_pipeline([Logger()], self.core)
        [chunk async for chunk in pipeline("m")]

        self.assertEqual(calls, ["one two three"])

    async def test_logger_pattern_request_and_response_lines(self):
        log = []

        class AgentLogger:
            def handle(self, model, handler):
                log.append(f"request | model={model}")

                def log_response(final):
                    log.append(f"response | {final}")

                return handler(model).then(log_response)

        buffered = build_pipeline([AgentLogger()], self.core)
        await buffered("gemini")

        streamed = build_pipeline([AgentLogger()], self.core)
        [chunk async for chunk in streamed("gemini")]

        self.assertEqual(
            log,
            [
                "request | model=gemini",
                "response | one two three",
                "request | model=gemini",
                "response | one two three",
            ],
        )


class TestMiddlewareProtocol(unittest.TestCase):
    def test_object_with_handle_satisfies_protocol(self):
        class Logger:
            def handle(self, model, handler):
                return handler(model)

        self.assertIsInstance(Logger(), Middleware)

    def test_object_without_handle_does_not_satisfy_protocol(self):
        class NotMiddleware:
            pass

        self.assertNotIsInstance(NotMiddleware(), Middleware)

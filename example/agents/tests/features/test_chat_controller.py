from dumpdie import dd

from app.agents.chat import ChatAgent

from tests.test_case import TestCase


class TestChatController(TestCase):
    @ChatAgent.fake(["Hello there, This is no stream chat, Hope you are doing well."])
    async def test_it_responds_without_stream(self):
        response = await self.post("/chat", json={"message": "hello"})

        response.assert_ok()
        response.assert_contents("Hello there, This is no stream chat, Hope you are doing well.")

    @ChatAgent.fake(["Hello there, This is no stream chat, Hope you are doing well."])
    async def test_stream_assertions_are_rejected_on_a_buffered_response(self):
        response = await self.post("/chat", json={"message": "hello"})

        # A buffered prompt() response is not a stream — stream assertions must fail.
        with self.assertRaises(AssertionError):
            response.assert_stream_contains("Hope you are doing well")
        with self.assertRaises(AssertionError):
            response.assert_stream("Hello there, This is no stream chat, Hope you are doing well.")

    @ChatAgent.fake(["Hello there, This is stream chat, Hope you are doing well."])
    async def test_it_responds_with_stream(self):
        response = await self.post("/chat/stream", json={"message": "hello"})

        response.assert_ok()
        response.assert_stream_contains('Hello there, This is stream chat, Hope you are doing well.')

    @ChatAgent.log("record_no_stream.json")
    async def test_it_records_without_stream(self):
        response = await self.post("/chat", json={"message": "Hi, I am Alex, This is unittest, Please respond by calling my name."})
        response.assert_ok()
        response.assert_contents("Alex")

    @ChatAgent.log("record_stream.json")
    async def test_chat_responds_for_other_greetings(self):
        response = await self.post("/chat/stream", json={
            "message": "Hi, I am Bedram, This is unittest, Please respond by calling my name."
        })

        response.assert_ok()
        response.assert_stream_contains("Bedram")

    @ChatAgent.log("job_search.json")
    async def test_user_can_perform_the_job_search(self):
        response = await self.post("/chat", json={
            "message": "suggest me python developer jobs"
        })

        response.assert_ok()

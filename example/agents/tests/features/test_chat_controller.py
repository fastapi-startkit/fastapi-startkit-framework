from app.agents.chat import RouterAgent

from tests.test_case import TestCase


class TestChatController(TestCase):
    @RouterAgent.fake({"*hello*": "Hello there!, Hope you are doing well."})
    async def test_chat_responds_for_basic_greetings(self):
        response = await self.post("/chat", json={"message": "hello"})

        response.assert_ok().assert_stream("Hello there!, Hope you are doing well.")

    @RouterAgent.record("other_greetings.json")
    async def test_chat_responds_for_other_greetings(self):
        response = await self.post("/chat", json={
            "message": "Hi, I am Bedram, This is unittest, Please respond by calling my name."
        })

        # Replays the recorded token stream chunk-for-chunk from the cassette.
        response.assert_ok().assert_stream("Hello ", "Bedram", ", nice to meet you!")

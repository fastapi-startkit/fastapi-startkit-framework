from app.agents.chat import RouterAgent

from tests.test_case import TestCase


class TestChatController(TestCase):
    @RouterAgent.fake({"*hello*": "Hello there!, Hope you are doing well."})
    async def test_chat_responds_for_basic_greetings(self):
        response = await self.post("/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"content": "Hello there!, Hope you are doing well."}
        )

    @RouterAgent.record('other_greetings.json')
    async def test_chat_responds_for_other_greetings(self):
        response = await self.post("/chat", json={
            "message": "Hi, I am Bedram, This is unittest, Please respond by calling my name."
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"content": "Hello there!, Hope you are doing well."}
        )

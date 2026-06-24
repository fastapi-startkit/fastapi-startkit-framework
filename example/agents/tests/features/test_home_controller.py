from tests.test_case import TestCase


class TestHomeController(TestCase):
    async def test_home(self) -> None:
        response = await self.get("/")

        self.assertEqual(response.status_code, 200)

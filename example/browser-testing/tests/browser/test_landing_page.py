from fastapi_startkit.playwright import visit

from .test_case import TestCase


class TestHome(TestCase):
    async def test_it_return_ok_from_home_page(self) -> None:
        await visit("/").assert_see("Welcome")

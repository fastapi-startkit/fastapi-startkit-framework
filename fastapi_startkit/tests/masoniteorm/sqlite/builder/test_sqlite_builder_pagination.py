from ...fixtures.model import User
from ..test_case import TestCase


class TestQueryBuilderPagination(TestCase):
    async def test_paginate(self):
        paginator = await User.query().paginate(1)

        self.assertTrue(paginator.count)
        self.assertTrue(paginator.serialize()["data"])
        self.assertTrue(paginator.serialize()["meta"])
        self.assertTrue(paginator.result)
        self.assertTrue(paginator.current_page)
        self.assertTrue(paginator.per_page)
        self.assertTrue(paginator.count)
        self.assertTrue(paginator.last_page)
        self.assertTrue(paginator.next_page)
        self.assertIsNone(paginator.previous_page)
        self.assertTrue(paginator.total)
        for user in paginator:
            self.assertIsInstance(user, User)

    async def test_simple_paginate(self):
        paginator = await User.query().simple_paginate(10, 1)

        self.assertIsInstance(paginator.to_json(), str)

        self.assertTrue(paginator.count)
        self.assertTrue(paginator.serialize()["data"])
        self.assertTrue(paginator.serialize()["meta"])
        self.assertTrue(paginator.result)
        self.assertTrue(paginator.current_page)
        self.assertTrue(paginator.per_page)
        self.assertTrue(paginator.count)
        self.assertIsNone(paginator.next_page)
        self.assertIsNone(paginator.previous_page)
        for user in paginator:
            self.assertIsInstance(user, User)

        self.assertIsInstance(paginator.to_json(), str)

    async def test_concurrent_paginate_calls(self):
        import asyncio

        paginators = await asyncio.gather(*(User.query().paginate(1) for _ in range(8)))

        self.assertTrue(all(paginator.total for paginator in paginators))
        self.assertTrue(all(paginator.count == 1 for paginator in paginators))

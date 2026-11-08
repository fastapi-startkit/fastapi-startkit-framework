from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class SlAccount(Model):
    __table__ = "sl_accounts"
    __timestamps__ = None
    id: int
    status: str
    balance: int


class TestSqliteLock(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create("sl_accounts") as table:
            table.id()
            table.string("status")
            table.integer("balance")
        await SlAccount.query().insert(
            [
                {"id": 1, "status": "open", "balance": 10},
                {"id": 2, "status": "open", "balance": 20},
                {"id": 3, "status": "closed", "balance": 30},
            ]
        )

    async def test_lock_for_update_is_a_no_op_inside_a_transaction(self):
        async with DB.connection("sqlite").transaction():
            account = await SlAccount.lock_for_update().where("id", 2).first()
            await SlAccount.where("id", 2).update({"balance": account.balance + 5})

        self.assertEqual((await SlAccount.find(2)).balance, 25)

    async def test_shared_lock_reads_the_same_rows(self):
        accounts = await SlAccount.shared_lock().where("status", "open").order_by("id").get()

        self.assertEqual([account.id for account in accounts], [1, 2])

    async def test_a_locked_query_keeps_grouped_wheres_counts_and_pages(self):
        query = SlAccount.where(lambda q: q.where("status", "closed").or_where("balance", 10)).lock_for_update()

        self.assertEqual(await query.count(), 2)
        page = await SlAccount.where("status", "open").lock_for_update().paginate(per_page=1, page=2)
        self.assertEqual((page.total, [account.id for account in page]), (2, [2]))

from unittest.mock import AsyncMock

from ..test_case import TestCase
from ..fixtures.db import DB
from ...fixtures.model import User


class TestSQLiteQueryBuilder(TestCase):
    async def test_where(self):
        sql = User.query().where("name", "Joe").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" = \'Joe\'')

    async def test_where_with_operator(self):
        sql = User.query().where("age", ">", 20).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."age" > \'20\'')

    async def test_select_columns(self):
        sql = User.query().select("name", "email").to_sql()
        self.assertEqual(sql, 'SELECT "users"."name", "users"."email" FROM "users"')

    async def test_limit(self):
        sql = User.query().limit(5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" LIMIT 5')

    async def test_offset(self):
        sql = User.query().limit(10).offset(5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" LIMIT 10 OFFSET 5')

    async def test_order_by_asc(self):
        sql = User.query().order_by("email", "asc").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "email" ASC')

    async def test_order_by_desc(self):
        sql = User.query().order_by("email", "desc").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "email" DESC')

    async def test_where_null(self):
        sql = User.query().where_null("name").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" IS NULL')

    async def test_where_not_null(self):
        sql = User.query().where_not_null("name").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" IS NOT NULL')

    async def test_where_in(self):
        sql = User.query().where_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM \"users\" WHERE \"users\".\"id\" IN ('1','2','3')")

    async def test_where_not_in(self):
        sql = User.query().where_not_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM \"users\" WHERE \"users\".\"id\" NOT IN ('1','2','3')")

    async def test_between(self):
        sql = User.query().between("id", 2, 5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."id" BETWEEN \'2\' AND \'5\'')

    async def test_not_between(self):
        sql = User.query().not_between("id", 2, 5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."id" NOT BETWEEN \'2\' AND \'5\'')

    async def test_join(self):
        sql = User.query().join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" INNER JOIN "profiles" ON "users"."id" = "profiles"."user_id"',
        )

    async def test_left_join(self):
        sql = User.query().left_join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" LEFT JOIN "profiles" ON "users"."id" = "profiles"."user_id"',
        )

    async def test_or_where(self):
        sql = User.query().where("age", "20").or_where("age", "<", 20).to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE "users"."age" = \'20\' OR "users"."age" < \'20\'',
        )

    async def test_where_column(self):
        sql = User.query().where_column("name", "username").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE name = username')

    async def test_when_true_applies_condition(self):
        sql = User.query().when(True, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."is_admin" = \'1\'')

    async def test_when_false_skips_condition(self):
        sql = User.query().when(False, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users"')

    async def test_update_sql_and_bindings(self):
        mock_update = AsyncMock(return_value=1)
        DB.connection("sqlite").update = mock_update

        await User.query().where("id", 1).update({"name": "Joe", "email": "joe@test.com"})

        mock_update.assert_called_once()
        sql, bindings = mock_update.call_args[0]
        self.assertEqual(sql, 'UPDATE "users" SET "name" = ?, "email" = ? WHERE "id" = ?')
        self.assertEqual(list(bindings), ["Joe", "joe@test.com", 1])

    async def test_delete_by_column(self):
        mock_delete = AsyncMock(return_value=1)
        DB.connection("sqlite").delete = mock_delete

        await User.query().where("id", 1).delete()

        mock_delete.assert_called_once()
        sql, bindings = mock_delete.call_args[0]
        self.assertEqual(sql, 'DELETE FROM "users" WHERE "id" = ?')
        self.assertEqual(list(bindings), [1])

    async def test_delete_where_in(self):
        mock_delete = AsyncMock(return_value=3)
        DB.connection("sqlite").delete = mock_delete

        await User.query().where_in("id", [1, 2, 3]).delete()

        mock_delete.assert_called_once()
        sql, bindings = mock_delete.call_args[0]
        self.assertEqual(sql, 'DELETE FROM "users" WHERE "id" IN (?, ?, ?)')
        self.assertEqual(list(bindings), [1, 2, 3])

    async def test_delete_with_multiple_wheres(self):
        mock_delete = AsyncMock(return_value=1)
        DB.connection("sqlite").delete = mock_delete

        await User.query().where("age", 20).where("profile", 1).delete()

        mock_delete.assert_called_once()
        sql, bindings = mock_delete.call_args[0]
        self.assertEqual(sql, 'DELETE FROM "users" WHERE "age" = ? AND "profile" = ?')
        self.assertEqual(list(bindings), [20, 1])

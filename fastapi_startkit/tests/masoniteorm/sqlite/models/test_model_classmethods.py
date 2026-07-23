"""
Tests that all QueryBuilder query-building methods are accessible directly
on Model subclasses as classmethods (e.g. User.where_null(...) instead of
User.query().where_null(...)).
"""

from ..test_case import TestCase
from ...fixtures.model import User


class TestModelClassmethods(TestCase):
    # --- filtering ---

    async def test_where_classmethod(self):
        sql = User.where("name", "Joe").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" = \'Joe\'')

    async def test_where_with_operator_classmethod(self):
        sql = User.where("age", ">", 20).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."age" > \'20\'')

    async def test_or_where_classmethod(self):
        sql = User.where("age", 20).or_where("age", "<", 10).to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE "users"."age" = \'20\' OR "users"."age" < \'10\'',
        )

    async def test_where_null_classmethod(self):
        sql = User.where_null("name").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" IS NULL')

    async def test_where_not_null_classmethod(self):
        sql = User.where_not_null("name").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."name" IS NOT NULL')

    async def test_where_in_classmethod(self):
        sql = User.where_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM \"users\" WHERE \"users\".\"id\" IN ('1','2','3')")

    async def test_where_not_in_classmethod(self):
        sql = User.where_not_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM \"users\" WHERE \"users\".\"id\" NOT IN ('1','2','3')")

    async def test_between_classmethod(self):
        sql = User.between("id", 2, 5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."id" BETWEEN \'2\' AND \'5\'')

    async def test_not_between_classmethod(self):
        sql = User.not_between("id", 2, 5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."id" NOT BETWEEN \'2\' AND \'5\'')

    async def test_where_column_classmethod(self):
        sql = User.where_column("name", "username").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE name = username')

    async def test_when_true_classmethod(self):
        sql = User.when(True, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" WHERE "users"."is_admin" = \'1\'')

    async def test_when_false_classmethod(self):
        sql = User.when(False, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users"')

    # --- selecting / projection ---

    async def test_select_classmethod(self):
        sql = User.select("name", "email").to_sql()
        self.assertEqual(sql, 'SELECT "users"."name", "users"."email" FROM "users"')

    async def test_distinct_classmethod(self):
        sql = User.distinct().to_sql()
        self.assertEqual(sql, 'SELECT DISTINCT * FROM "users"')

    # --- pagination helpers ---

    async def test_limit_classmethod(self):
        sql = User.limit(5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" LIMIT 5')

    async def test_offset_classmethod(self):
        sql = User.limit(10).offset(5).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" LIMIT 10 OFFSET 5')

    # --- ordering ---

    async def test_order_by_asc_classmethod(self):
        sql = User.order_by("name", "asc").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "name" ASC')

    async def test_order_by_desc_classmethod(self):
        sql = User.order_by("name", "desc").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "name" DESC')

    async def test_order_by_raw_classmethod(self):
        sql = User.order_by_raw("name DESC NULLS LAST").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY name DESC NULLS LAST')

    async def test_latest_classmethod(self):
        sql = User.latest().to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "created_at" DESC')

    async def test_oldest_classmethod(self):
        sql = User.oldest().to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" ORDER BY "created_at" ASC')

    # --- grouping ---

    async def test_group_by_classmethod(self):
        sql = User.group_by("name").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" GROUP BY "users"."name"')

    async def test_group_by_raw_classmethod(self):
        sql = User.group_by_raw("name, email").to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" GROUP BY name, email')

    async def test_having_classmethod(self):
        sql = User.group_by("name").having("id", ">", 1).to_sql()
        self.assertEqual(sql, 'SELECT * FROM "users" GROUP BY "users"."name" HAVING "users"."id" > \'1\'')

    # --- joins ---

    async def test_join_classmethod(self):
        sql = User.join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" INNER JOIN "profiles" ON "users"."id" = "profiles"."user_id"',
        )

    async def test_left_join_classmethod(self):
        sql = User.left_join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" LEFT JOIN "profiles" ON "users"."id" = "profiles"."user_id"',
        )

    # --- chaining produces correct SQL ---

    async def test_where_null_chained_with_or_where(self):
        sql = User.where_null("timespent").or_where("timespent", 0).to_sql()
        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE "users"."timespent" IS NULL OR "users"."timespent" = \'0\'',
        )

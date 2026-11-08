from unittest import IsolatedAsyncioTestCase

from fastapi_startkit.masoniteorm import HasMany, HasOne, Model, relationship

from ..fixtures.db import DB


class PostgresOfManyStatus(Model):
    __table__ = "statuses"


class PostgresOfManyUser(Model):
    __table__ = "users"

    statuses = HasMany["PostgresOfManyStatus"](local_key="id", foreign_key="user_id")

    @relationship
    def first_status(self) -> HasOne["PostgresOfManyStatus"]:
        return self.statuses.oldest_of_many()


class TestPostgresHasOneOfManySql(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.previous_db_manager = Model.db_manager
        Model.db_manager = DB

    async def asyncTearDown(self):
        Model.db_manager = self.previous_db_manager

    async def test_where_has_query_picks_the_oldest_non_null_row(self):
        sql = PostgresOfManyUser.where_has("first_status", lambda q: q.where("name", "done")).to_sql()

        self.assertEqual(
            sql,
            'SELECT * FROM "users" WHERE EXISTS (SELECT * FROM "statuses" WHERE "statuses"."id" = '
            '(SELECT "statuses_of_many"."id" FROM "statuses" AS "statuses_of_many" WHERE '
            'statuses_of_many.user_id = statuses.user_id AND "statuses_of_many"."created_at" IS NOT NULL '
            'ORDER BY "statuses_of_many"."created_at" ASC, "statuses_of_many"."id" ASC LIMIT 1) AND '
            'statuses.user_id = users.id AND "statuses"."name" = \'done\')',
        )

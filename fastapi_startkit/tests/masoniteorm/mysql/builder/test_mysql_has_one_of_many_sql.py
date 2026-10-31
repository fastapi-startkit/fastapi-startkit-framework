from fastapi_startkit.masoniteorm import HasMany, HasOne, Model, relationship

from ..test_case import TestCase


class MySQLOfManyStatus(Model):
    __table__ = "statuses"


class MySQLOfManyUser(Model):
    __table__ = "users"

    statuses = HasMany["MySQLOfManyStatus"](local_key="id", foreign_key="user_id")

    @relationship
    def latest_status(self) -> HasOne["MySQLOfManyStatus"]:
        return self.statuses.latest_of_many()


class TestMySQLHasOneOfManySql(TestCase):
    async def test_eager_query_picks_one_row_per_parent(self):
        sql = MySQLOfManyUser.latest_status.where_in("statuses.user_id", [1, 2]).to_sql()

        self.assertEqual(
            sql,
            "SELECT * FROM `statuses` WHERE `statuses`.`id` = (SELECT `statuses_of_many`.`id` FROM `statuses` AS "
            "`statuses_of_many` WHERE statuses_of_many.user_id = statuses.user_id AND "
            "`statuses_of_many`.`created_at` IS NOT NULL ORDER BY `statuses_of_many`.`created_at` DESC, "
            "`statuses_of_many`.`id` DESC LIMIT 1) AND `statuses`.`user_id` IN ('1','2')",
        )

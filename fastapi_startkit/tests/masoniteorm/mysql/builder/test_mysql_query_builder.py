from unittest.mock import AsyncMock

from fastapi_startkit.masoniteorm import Model

from ..test_case import TestCase
from ..fixtures.db import DB
from ...fixtures.model import User


class Payment(Model):
    __table__ = "payments"
    __connection__ = "mysql"


class TestMySQLQueryBuilder(TestCase):
    # --- SELECT / WHERE ---

    async def test_where(self):
        sql = User.query().where("name", "Joe").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`name` = 'Joe'")

    async def test_where_with_operator(self):
        sql = User.query().where("age", ">", "20").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` > '20'")

    async def test_where_lt(self):
        sql = User.query().where("age", "<", "20").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` < '20'")

    async def test_where_lte(self):
        sql = User.query().where("age", "<=", "20").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` <= '20'")

    async def test_where_gte(self):
        sql = User.query().where("age", ">=", "20").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` >= '20'")

    async def test_where_ne(self):
        sql = User.query().where("age", "!=", "20").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` != '20'")

    async def test_or_where(self):
        sql = User.query().where("age", "20").or_where("age", "<", 20).to_sql()
        self.assertEqual(
            sql,
            "SELECT * FROM `users` WHERE `users`.`age` = '20' OR `users`.`age` < '20'",
        )

    async def test_where_null(self):
        sql = User.query().where_null("name").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`name` IS NULL")

    async def test_where_not_null(self):
        sql = User.query().where_not_null("name").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`name` IS NOT NULL")

    async def test_where_in(self):
        sql = User.query().where_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`id` IN ('1','2','3')")

    async def test_where_not_in(self):
        sql = User.query().where_not_in("id", [1, 2, 3]).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`id` NOT IN ('1','2','3')")

    async def test_where_like(self):
        sql = User.query().where("age", "like", "%name%").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` LIKE '%name%'")

    async def test_where_not_like(self):
        sql = User.query().where("age", "not like", "%name%").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`age` NOT LIKE '%name%'")

    async def test_where_column(self):
        sql = User.query().where_column("name", "username").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE name = username")

    async def test_between(self):
        sql = User.query().between("id", 2, 5).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`id` BETWEEN '2' AND '5'")

    async def test_not_between(self):
        sql = User.query().not_between("id", 2, 5).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`id` NOT BETWEEN '2' AND '5'")

    async def test_when_true_applies_condition(self):
        sql = User.query().when(True, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` WHERE `users`.`is_admin` = '1'")

    async def test_when_false_skips_condition(self):
        sql = User.query().when(False, lambda q: q.where("is_admin", 1)).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users`")

    # --- SELECT columns ---

    async def test_select_columns(self):
        sql = User.query().select("name", "email").to_sql()
        self.assertEqual(sql, "SELECT `users`.`name`, `users`.`email` FROM `users`")

    # --- LIMIT / OFFSET ---

    async def test_limit(self):
        sql = User.query().limit(5).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` LIMIT 5")

    async def test_offset(self):
        sql = User.query().limit(10).offset(5).to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` LIMIT 10 OFFSET 5")

    # --- ORDER BY ---

    async def test_order_by_asc(self):
        sql = User.query().order_by("email", "asc").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` ORDER BY `email` ASC")

    async def test_order_by_desc(self):
        sql = User.query().order_by("email", "desc").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` ORDER BY `email` DESC")

    async def test_latest(self):
        sql = User.query().latest("email").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` ORDER BY `email` DESC")

    async def test_oldest(self):
        sql = User.query().oldest("email").to_sql()
        self.assertEqual(sql, "SELECT * FROM `users` ORDER BY `email` ASC")

    # --- JOINS ---

    async def test_join(self):
        sql = User.query().join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            "SELECT * FROM `users` INNER JOIN `profiles` ON `users`.`id` = `profiles`.`user_id`",
        )

    async def test_left_join(self):
        sql = User.query().left_join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            "SELECT * FROM `users` LEFT JOIN `profiles` ON `users`.`id` = `profiles`.`user_id`",
        )

    async def test_right_join(self):
        sql = User.query().right_join("profiles", "users.id", "=", "profiles.user_id").to_sql()
        self.assertEqual(
            sql,
            "SELECT * FROM `users` RIGHT JOIN `profiles` ON `users`.`id` = `profiles`.`user_id`",
        )

    # --- AGGREGATES (mock select_one to capture generated SQL) ---

    async def test_count(self):
        mock_select_one = AsyncMock(return_value={"id": 5})
        DB.connection("mysql").select_one = mock_select_one

        await User.query().count("id")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(sql, "SELECT COUNT(`users`.`id`) AS id FROM `users`")
        self.assertEqual(list(bindings), [])

    async def test_sum(self):
        mock_select_one = AsyncMock(return_value={"age": 100})
        DB.connection("mysql").select_one = mock_select_one

        await User.query().sum("age")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(sql, "SELECT SUM(`users`.`age`) AS age FROM `users`")
        self.assertEqual(list(bindings), [])

    async def test_max(self):
        mock_select_one = AsyncMock(return_value={"age": 99})
        DB.connection("mysql").select_one = mock_select_one

        await User.query().max("age")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(sql, "SELECT MAX(`users`.`age`) AS age FROM `users`")
        self.assertEqual(list(bindings), [])

    async def test_min(self):
        mock_select_one = AsyncMock(return_value={"age": 1})
        DB.connection("mysql").select_one = mock_select_one

        await User.query().min("age")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(sql, "SELECT MIN(`users`.`age`) AS age FROM `users`")
        self.assertEqual(list(bindings), [])

    async def test_avg(self):
        mock_select_one = AsyncMock(return_value={"age": 30})
        DB.connection("mysql").select_one = mock_select_one

        await User.query().avg("age")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(sql, "SELECT AVG(`users`.`age`) AS age FROM `users`")
        self.assertEqual(list(bindings), [])

    # --- GROUP BY / HAVING ---

    async def test_group_by(self):
        mock_select_one = AsyncMock(return_value={"salary": 500})
        DB.connection("mysql").select_one = mock_select_one

        await Payment.query().select("user_id").group_by("user_id").min("salary")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(
            sql,
            "SELECT `payments`.`user_id`, MIN(`payments`.`salary`) AS salary FROM `payments` GROUP BY `payments`.`user_id`",
        )
        self.assertEqual(list(bindings), [])

    async def test_having(self):
        mock_select_one = AsyncMock(return_value={"salary": 2000})
        DB.connection("mysql").select_one = mock_select_one

        await Payment.query().select("user_id").group_by("user_id").having("salary", ">=", "1000").avg("salary")

        sql, bindings = mock_select_one.call_args[0]
        self.assertEqual(
            sql,
            "SELECT `payments`.`user_id`, AVG(`payments`.`salary`) AS salary FROM `payments` GROUP BY `payments`.`user_id` HAVING `payments`.`salary` >= '1000'",
        )
        self.assertEqual(list(bindings), [])

    # --- DML: INSERT / UPDATE / DELETE ---

    async def test_insert_sql(self):
        mock_insert = AsyncMock(return_value=1)
        DB.connection("mysql").insert = mock_insert

        await User.query().insert({"name": "Joe"})

        mock_insert.assert_called_once()
        sql, bindings = mock_insert.call_args[0]
        self.assertEqual(sql, "INSERT INTO `users` (`name`) VALUES (?)")
        self.assertEqual(list(bindings), ["Joe"])

    async def test_bulk_insert_sql(self):
        mock_insert = AsyncMock(return_value=3)
        DB.connection("mysql").insert = mock_insert

        await User.query().insert([{"name": "Joe"}, {"name": "Bill"}, {"name": "John"}])

        mock_insert.assert_called_once()
        sql, bindings = mock_insert.call_args[0]
        self.assertEqual(sql, "INSERT INTO `users` (`name`) VALUES (?), (?), (?)")
        self.assertEqual(list(bindings), ["Joe", "Bill", "John"])

    async def test_update_sql(self):
        mock_update = AsyncMock(return_value=1)
        DB.connection("mysql").update = mock_update

        await User.query().where("id", 1).update({"name": "Joe", "email": "joe@test.com"})

        mock_update.assert_called_once()
        sql, bindings = mock_update.call_args[0]
        self.assertEqual(
            sql,
            "UPDATE `users` SET `users`.`name` = ?, `users`.`email` = ? WHERE `users`.`id` = ?",
        )
        self.assertEqual(list(bindings), ["Joe", "joe@test.com", 1])

    async def test_delete_by_where(self):
        mock_delete = AsyncMock(return_value=1)
        DB.connection("mysql").delete = mock_delete

        await User.query().where("id", 1).delete()

        mock_delete.assert_called_once()
        sql, bindings = mock_delete.call_args[0]
        self.assertEqual(sql, "DELETE FROM `users` WHERE `users`.`id` = ?")
        self.assertEqual(list(bindings), [1])

    async def test_delete_where_in(self):
        mock_delete = AsyncMock(return_value=3)
        DB.connection("mysql").delete = mock_delete

        await User.query().where_in("id", [1, 2, 3]).delete()

        mock_delete.assert_called_once()
        sql, bindings = mock_delete.call_args[0]
        self.assertEqual(sql, "DELETE FROM `users` WHERE `users`.`id` IN (?, ?, ?)")
        self.assertEqual(list(bindings), [1, 2, 3])

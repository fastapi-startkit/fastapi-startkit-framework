import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.processors.MSSQLPostProcessor import MSSQLPostProcessor


class TestMSSQLGrammarSelect(unittest.TestCase):
    def setUp(self):
        query = QueryBuilder(connection=None, grammar=MSSQLGrammar, processor=MSSQLPostProcessor)
        query._table = "users"
        self.query = query

    def test_select_all(self):
        self.assertEqual(self.query.to_sql(), "SELECT * FROM [users]")

    def test_select_columns(self):
        self.assertEqual(
            self.query.select("name", "email").to_sql(),
            "SELECT [users].[name], [users].[email] FROM [users]",
        )

    def test_select_distinct(self):
        self.assertEqual(
            self.query.select("name").distinct().to_sql(),
            "SELECT DISTINCT [users].[name] FROM [users]",
        )

    def test_where_with_operator(self):
        self.assertEqual(
            self.query.where("age", ">", 18).to_sql(),
            "SELECT * FROM [users] WHERE [users].[age] > '18'",
        )

    def test_where_equals(self):
        self.assertEqual(
            self.query.where("name", "Joe").to_sql(),
            "SELECT * FROM [users] WHERE [users].[name] = 'Joe'",
        )

    def test_or_where(self):
        self.assertEqual(
            self.query.where("age", 18).or_where("age", "<", 5).to_sql(),
            "SELECT * FROM [users] WHERE [users].[age] = '18' OR [users].[age] < '5'",
        )

    def test_where_null(self):
        self.assertEqual(
            self.query.where_null("name").to_sql(),
            "SELECT * FROM [users] WHERE [users].[name] IS NULL",
        )

    def test_where_in(self):
        self.assertEqual(
            self.query.where_in("id", [1, 2, 3]).to_sql(),
            "SELECT * FROM [users] WHERE [users].[id] IN ('1','2','3')",
        )

    def test_where_between(self):
        self.assertEqual(
            self.query.between("age", 10, 20).to_sql(),
            "SELECT * FROM [users] WHERE [users].[age] BETWEEN '10' AND '20'",
        )

    def test_where_like(self):
        self.assertEqual(
            self.query.where("name", "like", "%Jo%").to_sql(),
            "SELECT * FROM [users] WHERE [users].[name] LIKE '%Jo%'",
        )

    def test_limit_uses_top(self):
        self.assertEqual(self.query.limit(5).to_sql(), "SELECT TOP 5 * FROM [users]")

    def test_offset_uses_fetch_next(self):
        self.assertEqual(
            self.query.limit(5).offset(10).to_sql(),
            "SELECT * FROM [users] OFFSET 10 ROWS FETCH NEXT 5 ROWS ONLY",
        )

    def test_order_by(self):
        self.assertEqual(
            self.query.order_by("name", "desc").to_sql(),
            "SELECT * FROM [users] ORDER BY [name] DESC",
        )

    def test_group_by(self):
        self.assertEqual(
            self.query.group_by("age").to_sql(),
            "SELECT * FROM [users] GROUP BY [users].[age]",
        )

    def test_inner_join(self):
        qb = self.query.join("profiles", "users.id", "=", "profiles.user_id")
        self.assertEqual(
            qb.to_sql(),
            "SELECT * FROM [users] INNER JOIN [profiles] ON [users].[id] = [profiles].[user_id]",
        )


class TestMSSQLGrammarWrites(unittest.TestCase):
    def setUp(self):
        query = QueryBuilder(connection=None, grammar=MSSQLGrammar, processor=MSSQLPostProcessor)
        query._table = "users"
        self.query = query

    def test_insert(self):
        grammar = MSSQLGrammar(columns={"name": "Joe", "email": "j@x.com"}, table="users")
        self.assertEqual(
            grammar.compile("insert")._sql,
            "INSERT INTO [users] ([users].[name], [users].[email]) VALUES ('Joe', 'j@x.com')",
        )

    def test_delete(self):
        qb = self.query.where("id", 1).set_action("delete")
        self.assertEqual(qb.to_sql(), "DELETE FROM [users] WHERE [users].[id] = '1'")


class TestMSSQLGrammarPrimitives(unittest.TestCase):
    def setUp(self):
        self.grammar = MSSQLGrammar()

    def test_table_string_wraps_in_brackets(self):
        self.assertEqual(self.grammar.wrap_table("users"), "[users]")

    def test_truncate_table(self):
        self.assertEqual(self.grammar.truncate_table("users"), "TRUNCATE TABLE [users]")

    def test_compile_random_uses_newid(self):
        self.assertEqual(self.grammar.compile_random(5), "NEWID()")

    def test_limit_string_without_offset(self):
        self.assertEqual(self.grammar.limit_string(), "TOP {limit}")

    def test_limit_string_with_offset_is_empty(self):
        self.assertEqual(self.grammar.limit_string(offset=True), "")

    def test_increment_and_decrement_strings(self):
        self.assertEqual(self.grammar.increment_string(), "{column} = {column} + {value}")
        self.assertEqual(self.grammar.decrement_string(), "{column} = {column} - {value}")

    def test_insert_and_bulk_insert_formats(self):
        self.assertEqual(
            self.grammar.insert_format(),
            "INSERT INTO {table} ({columns}) VALUES ({values})",
        )
        self.assertEqual(
            self.grammar.bulk_insert_format(),
            "INSERT INTO {table} ({columns}) VALUES {values}",
        )

    def test_join_keywords_mapping(self):
        self.assertEqual(self.grammar.join_keywords["left"], "LEFT JOIN")
        self.assertEqual(self.grammar.join_keywords["right"], "RIGHT JOIN")
        self.assertEqual(self.grammar.join_keywords["outer"], "OUTER JOIN")

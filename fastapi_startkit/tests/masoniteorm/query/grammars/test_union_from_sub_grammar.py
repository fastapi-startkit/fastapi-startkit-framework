import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar

GRAMMARS = {
    "sqlite": SQLiteGrammar,
    "mysql": MySQLGrammar,
    "postgres": PostgresGrammar,
    "mssql": MSSQLGrammar,
}

EXPECTED = {
    "sqlite": {
        "union_all": 'SELECT * FROM (SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) UNION ALL SELECT * FROM (SELECT "plays"."user_id" FROM "plays" WHERE "plays"."model_type" = ?)',
        "union": 'SELECT * FROM (SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) UNION SELECT * FROM (SELECT "plays"."user_id" FROM "plays" WHERE "plays"."model_type" = ?)',
        "from_sub": 'SELECT DISTINCT "events"."user_id" FROM (SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) AS "events"',
        "combined": 'SELECT "events"."skill", count(distinct user_id) * ? as learners FROM (SELECT * FROM (SELECT "reviews"."user_id", ? as skill FROM "reviews" WHERE "reviews"."created_at" >= ?) UNION ALL SELECT * FROM (SELECT "messages"."user_id", ? as skill FROM "messages" WHERE "messages"."created_at" >= ?)) AS "events" WHERE "events"."user_id" > ? GROUP BY "events"."skill"',
    },
    "mysql": {
        "union_all": "(SELECT `reviews`.`user_id` FROM `reviews` WHERE `reviews`.`mode` = ?) UNION ALL (SELECT `plays`.`user_id` FROM `plays` WHERE `plays`.`model_type` = ?)",
        "union": "(SELECT `reviews`.`user_id` FROM `reviews` WHERE `reviews`.`mode` = ?) UNION (SELECT `plays`.`user_id` FROM `plays` WHERE `plays`.`model_type` = ?)",
        "from_sub": "SELECT DISTINCT `events`.`user_id` FROM (SELECT `reviews`.`user_id` FROM `reviews` WHERE `reviews`.`mode` = ?) AS `events`",
        "combined": "SELECT `events`.`skill`, count(distinct user_id) * ? as learners FROM ((SELECT `reviews`.`user_id`, ? as skill FROM `reviews` WHERE `reviews`.`created_at` >= ?) UNION ALL (SELECT `messages`.`user_id`, ? as skill FROM `messages` WHERE `messages`.`created_at` >= ?)) AS `events` WHERE `events`.`user_id` > ? GROUP BY `events`.`skill`",
    },
    "postgres": {
        "union_all": '(SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) UNION ALL (SELECT "plays"."user_id" FROM "plays" WHERE "plays"."model_type" = ?)',
        "union": '(SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) UNION (SELECT "plays"."user_id" FROM "plays" WHERE "plays"."model_type" = ?)',
        "from_sub": 'SELECT DISTINCT "events"."user_id" FROM (SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = ?) AS "events"',
        "combined": 'SELECT "events"."skill", count(distinct user_id) * ? as learners FROM ((SELECT "reviews"."user_id", ? as skill FROM "reviews" WHERE "reviews"."created_at" >= ?) UNION ALL (SELECT "messages"."user_id", ? as skill FROM "messages" WHERE "messages"."created_at" >= ?)) AS "events" WHERE "events"."user_id" > ? GROUP BY "events"."skill"',
    },
    "mssql": {
        "union_all": "SELECT * FROM (SELECT [reviews].[user_id] FROM [reviews] WHERE [reviews].[mode] = ?) AS [temp_table] UNION ALL SELECT * FROM (SELECT [plays].[user_id] FROM [plays] WHERE [plays].[model_type] = ?) AS [temp_table]",
        "union": "SELECT * FROM (SELECT [reviews].[user_id] FROM [reviews] WHERE [reviews].[mode] = ?) AS [temp_table] UNION SELECT * FROM (SELECT [plays].[user_id] FROM [plays] WHERE [plays].[model_type] = ?) AS [temp_table]",
        "from_sub": "SELECT DISTINCT [events].[user_id] FROM (SELECT [reviews].[user_id] FROM [reviews] WHERE [reviews].[mode] = ?) AS [events]",
        "combined": "SELECT [events].[skill], count(distinct user_id) * ? as learners FROM (SELECT * FROM (SELECT [reviews].[user_id], ? as skill FROM [reviews] WHERE [reviews].[created_at] >= ?) AS [temp_table] UNION ALL SELECT * FROM (SELECT [messages].[user_id], ? as skill FROM [messages] WHERE [messages].[created_at] >= ?) AS [temp_table]) AS [events] WHERE [events].[user_id] > ? GROUP BY [events].[skill]",
    },
}


class GrammarConnection:
    def __init__(self, grammar):
        self.grammar = grammar

    def query(self):
        return QueryBuilder(connection=self, grammar=self.grammar, processor=None)


def qb(grammar, table=""):
    q = GrammarConnection(grammar).query()
    q._table = table
    return q


def listen_reviews(grammar):
    return qb(grammar, "reviews").select("user_id").where("mode", "listen")


def article_plays(grammar):
    return qb(grammar, "plays").select("user_id").where("model_type", "article")


def skill_events(grammar, table, skill):
    return (
        qb(grammar, table).select("user_id").select_raw("? as skill", [skill]).where("created_at", ">=", "2026-01-01")
    )


class TestUnionFromSubGrammar(unittest.TestCase):
    def assert_compiles(self, name, build, bindings):
        for dialect, grammar in GRAMMARS.items():
            with self.subTest(dialect=dialect):
                query = build(grammar)
                self.assertEqual(query.to_qmark(), EXPECTED[dialect][name])
                self.assertEqual(list(query.get_bindings()), bindings)

    def test_union_all_appends_every_row_of_the_second_query(self):
        self.assert_compiles(
            "union_all",
            lambda grammar: listen_reviews(grammar).union_all(article_plays(grammar)),
            ["listen", "article"],
        )

    def test_union_keeps_distinct_rows(self):
        self.assert_compiles(
            "union",
            lambda grammar: listen_reviews(grammar).union(article_plays(grammar)),
            ["listen", "article"],
        )

    def test_from_sub_selects_from_an_aliased_subquery(self):
        self.assert_compiles(
            "from_sub",
            lambda grammar: qb(grammar).from_sub(listen_reviews(grammar), "events").select("user_id").distinct(),
            ["listen"],
        )

    def test_from_sub_over_a_union_keeps_bindings_in_sql_order(self):
        self.assert_compiles(
            "combined",
            lambda grammar: (
                qb(grammar)
                .from_sub(
                    skill_events(grammar, "reviews", "listen").union_all(skill_events(grammar, "messages", "speak")),
                    "events",
                )
                .select("skill")
                .select_raw("count(distinct user_id) * ? as learners", [1])
                .where("user_id", ">", 0)
                .group_by("skill")
            ),
            [1, "listen", "2026-01-01", "speak", "2026-01-01", 0],
        )

    def test_union_all_with_a_callable(self):
        self.assert_compiles(
            "union_all",
            lambda grammar: listen_reviews(grammar).union_all(
                lambda other: other.table("plays").select("user_id").where("model_type", "article")
            ),
            ["listen", "article"],
        )

    def test_from_sub_with_a_callable(self):
        self.assert_compiles(
            "from_sub",
            lambda grammar: (
                qb(grammar)
                .from_sub(lambda sub: sub.table("reviews").select("user_id").where("mode", "listen"), "events")
                .select("user_id")
                .distinct()
            ),
            ["listen"],
        )

    def test_to_sql_inlines_every_member(self):
        sql = listen_reviews(PostgresGrammar).union_all(article_plays(PostgresGrammar)).to_sql()
        self.assertEqual(
            sql,
            '(SELECT "reviews"."user_id" FROM "reviews" WHERE "reviews"."mode" = \'listen\') UNION ALL (SELECT "plays"."user_id" FROM "plays" WHERE "plays"."model_type" = \'article\')',
        )

    def test_rejects_anything_but_a_builder_or_callable(self):
        builder = listen_reviews(PostgresGrammar)
        with self.assertRaises(TypeError):
            builder.union_all("SELECT 1")
        with self.assertRaises(TypeError):
            builder.union("SELECT 1")
        with self.assertRaises(TypeError):
            qb(PostgresGrammar).from_sub("SELECT 1", "events")

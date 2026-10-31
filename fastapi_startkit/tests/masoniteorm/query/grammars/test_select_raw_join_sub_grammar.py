import unittest
from unittest.mock import AsyncMock, Mock

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

OCR = (
    "COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr"
)
DUE = (
    "SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day FROM memories "
    "WHERE memories.due_date BETWEEN ? AND ? GROUP BY memories.lexeme_id"
)

EXPECTED = {
    "sqlite": {
        "select_raw": 'SELECT "lexemes".*, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" WHERE "lexemes"."language" = ?',
        "select_raw_only": 'SELECT COUNT(*) AS total, MAX(lexemes.id) AS last_id FROM "lexemes"',
        "join_sub": 'SELECT * FROM "lexemes" INNER JOIN (SELECT "memories"."lexeme_id" FROM "memories" WHERE "memories"."skill_id" = ? GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = ?',
        "join_sub_sql": 'SELECT * FROM "lexemes" INNER JOIN (SELECT "memories"."lexeme_id" FROM "memories" WHERE "memories"."skill_id" = \'3\' GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = \'fr\'',
        "left_join_sub": 'SELECT * FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day FROM memories WHERE memories.due_date BETWEEN ? AND ? GROUP BY memories.lexeme_id) AS "due" ON "due"."lexeme_id" = "lexemes"."id"',
        "combined": 'SELECT "lexemes".*, "due"."due_day" AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM "memories" WHERE memories.due_date >= ? AND "memories"."skill_id" IS NULL GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = ? AND due.due_day BETWEEN ? AND ? ORDER BY "due"."due_day" ASC, "lexemes"."text" ASC, "lexemes"."id" ASC LIMIT 25 OFFSET 50',
        "combined_sql": 'SELECT "lexemes".*, "due"."due_day" AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM "memories" WHERE memories.due_date >= ? AND "memories"."skill_id" IS NULL GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = \'fr\' AND due.due_day BETWEEN ? AND ? ORDER BY "due"."due_day" ASC, "lexemes"."text" ASC, "lexemes"."id" ASC LIMIT 25 OFFSET 50',
    },
    "mysql": {
        "select_raw": "SELECT `lexemes`.*, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM `lexemes` WHERE `lexemes`.`language` = ?",
        "select_raw_only": "SELECT COUNT(*) AS total, MAX(lexemes.id) AS last_id FROM `lexemes`",
        "join_sub": "SELECT * FROM `lexemes` INNER JOIN (SELECT `memories`.`lexeme_id` FROM `memories` WHERE `memories`.`skill_id` = ? GROUP BY `memories`.`lexeme_id`) AS `due` ON `due`.`lexeme_id` = `lexemes`.`id` WHERE `lexemes`.`language` = ?",
        "join_sub_sql": "SELECT * FROM `lexemes` INNER JOIN (SELECT `memories`.`lexeme_id` FROM `memories` WHERE `memories`.`skill_id` = '3' GROUP BY `memories`.`lexeme_id`) AS `due` ON `due`.`lexeme_id` = `lexemes`.`id` WHERE `lexemes`.`language` = 'fr'",
        "left_join_sub": "SELECT * FROM `lexemes` LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day FROM memories WHERE memories.due_date BETWEEN ? AND ? GROUP BY memories.lexeme_id) AS `due` ON `due`.`lexeme_id` = `lexemes`.`id`",
        "combined": "SELECT `lexemes`.*, `due`.`due_day` AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM `lexemes` LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM `memories` WHERE memories.due_date >= ? AND `memories`.`skill_id` IS NULL GROUP BY `memories`.`lexeme_id`) AS `due` ON `due`.`lexeme_id` = `lexemes`.`id` WHERE `lexemes`.`language` = ? AND due.due_day BETWEEN ? AND ? ORDER BY `due`.`due_day` ASC, `lexemes`.`text` ASC, `lexemes`.`id` ASC LIMIT 25 OFFSET 50",
        "combined_sql": "SELECT `lexemes`.*, `due`.`due_day` AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM `lexemes` LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM `memories` WHERE memories.due_date >= ? AND `memories`.`skill_id` IS NULL GROUP BY `memories`.`lexeme_id`) AS `due` ON `due`.`lexeme_id` = `lexemes`.`id` WHERE `lexemes`.`language` = 'fr' AND due.due_day BETWEEN ? AND ? ORDER BY `due`.`due_day` ASC, `lexemes`.`text` ASC, `lexemes`.`id` ASC LIMIT 25 OFFSET 50",
    },
    "postgres": {
        "select_raw": 'SELECT "lexemes".*, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" WHERE "lexemes"."language" = ?',
        "select_raw_only": 'SELECT COUNT(*) AS total, MAX(lexemes.id) AS last_id FROM "lexemes"',
        "join_sub": 'SELECT * FROM "lexemes" INNER JOIN (SELECT "memories"."lexeme_id" FROM "memories" WHERE "memories"."skill_id" = ? GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = ?',
        "join_sub_sql": 'SELECT * FROM "lexemes" INNER JOIN (SELECT "memories"."lexeme_id" FROM "memories" WHERE "memories"."skill_id" = \'3\' GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = \'fr\'',
        "left_join_sub": 'SELECT * FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day FROM memories WHERE memories.due_date BETWEEN ? AND ? GROUP BY memories.lexeme_id) AS "due" ON "due"."lexeme_id" = "lexemes"."id"',
        "combined": 'SELECT "lexemes".*, "due"."due_day" AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM "memories" WHERE memories.due_date >= ? AND "memories"."skill_id" IS NULL GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = ? AND due.due_day BETWEEN ? AND ? ORDER BY "due"."due_day" ASC, "lexemes"."text" ASC, "lexemes"."id" ASC LIMIT 25 OFFSET 50',
        "combined_sql": 'SELECT "lexemes".*, "due"."due_day" AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), \'pending\') AS ocr FROM "lexemes" LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM "memories" WHERE memories.due_date >= ? AND "memories"."skill_id" IS NULL GROUP BY "memories"."lexeme_id") AS "due" ON "due"."lexeme_id" = "lexemes"."id" WHERE "lexemes"."language" = \'fr\' AND due.due_day BETWEEN ? AND ? ORDER BY "due"."due_day" ASC, "lexemes"."text" ASC, "lexemes"."id" ASC LIMIT 25 OFFSET 50',
    },
    "mssql": {
        "select_raw": "SELECT [lexemes].*, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM [lexemes] WHERE [lexemes].[language] = ?",
        "select_raw_only": "SELECT COUNT(*) AS total, MAX(lexemes.id) AS last_id FROM [lexemes]",
        "join_sub": "SELECT * FROM [lexemes] INNER JOIN (SELECT [memories].[lexeme_id] FROM [memories] WHERE [memories].[skill_id] = ? GROUP BY [memories].[lexeme_id]) AS [due] ON [due].[lexeme_id] = [lexemes].[id] WHERE [lexemes].[language] = ?",
        "join_sub_sql": "SELECT * FROM [lexemes] INNER JOIN (SELECT [memories].[lexeme_id] FROM [memories] WHERE [memories].[skill_id] = '3' GROUP BY [memories].[lexeme_id]) AS [due] ON [due].[lexeme_id] = [lexemes].[id] WHERE [lexemes].[language] = 'fr'",
        "left_join_sub": "SELECT * FROM [lexemes] LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day FROM memories WHERE memories.due_date BETWEEN ? AND ? GROUP BY memories.lexeme_id) AS [due] ON [due].[lexeme_id] = [lexemes].[id]",
        "combined": "SELECT [lexemes].*, [due].[due_day] AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM [lexemes] LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM [memories] WHERE memories.due_date >= ? AND [memories].[skill_id] IS NULL GROUP BY [memories].[lexeme_id]) AS [due] ON [due].[lexeme_id] = [lexemes].[id] WHERE [lexemes].[language] = ? AND due.due_day BETWEEN ? AND ? ORDER BY [due].[due_day] ASC, [lexemes].[text] ASC, [lexemes].[id] ASC OFFSET 50 ROWS FETCH NEXT 25 ROWS ONLY",
        "combined_sql": "SELECT [lexemes].*, [due].[due_day] AS due_date, COALESCE((SELECT s.status FROM lexeme_statuses s WHERE s.lexeme_id = lexemes.id AND s.type = ?), 'pending') AS ocr FROM [lexemes] LEFT JOIN (SELECT memories.lexeme_id, MIN(memories.due_date) AS due_day, COUNT(*) AS learners FROM [memories] WHERE memories.due_date >= ? AND [memories].[skill_id] IS NULL GROUP BY [memories].[lexeme_id]) AS [due] ON [due].[lexeme_id] = [lexemes].[id] WHERE [lexemes].[language] = 'fr' AND due.due_day BETWEEN ? AND ? ORDER BY [due].[due_day] ASC, [lexemes].[text] ASC, [lexemes].[id] ASC OFFSET 50 ROWS FETCH NEXT 25 ROWS ONLY",
    },
}


def qb(grammar, table):
    query = QueryBuilder(connection=None, grammar=grammar, processor=None)
    query._table = table
    return query


def due_subquery(grammar):
    return (
        qb(grammar, "memories")
        .select_raw("memories.lexeme_id, MIN(memories.due_date) AS due_day")
        .select_raw("COUNT(*) AS learners")
        .where_raw("memories.due_date >= ?", ["2026-01-01"])
        .where_null("memories.skill_id")
        .group_by("memories.lexeme_id")
    )


def listing_query(grammar):
    return (
        qb(grammar, "lexemes")
        .select("lexemes.*", "due.due_day as due_date")
        .select_raw(OCR, ["ocr"])
        .left_join_sub(due_subquery(grammar), "due", "due.lexeme_id", "=", "lexemes.id")
        .where("lexemes.language", "fr")
        .where_raw("due.due_day BETWEEN ? AND ?", ["2026-01-01", "2026-01-31"])
        .order_by("due.due_day")
        .order_by("lexemes.text")
        .order_by("lexemes.id")
        .limit(25)
        .offset(50)
    )


class TestSelectRawGrammar(unittest.TestCase):
    def test_select_raw_bindings_precede_where_bindings(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = (
                    qb(grammar, "lexemes").select("lexemes.*").select_raw(OCR, ["ocr"]).where("lexemes.language", "fr")
                )

                self.assertEqual(query.to_qmark(), EXPECTED[name]["select_raw"])
                self.assertEqual(list(query.get_bindings()), ["ocr", "fr"])

    def test_select_raw_is_not_split_on_commas_and_selects_only_itself(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = qb(grammar, "lexemes").select_raw("COUNT(*) AS total, MAX(lexemes.id) AS last_id")

                self.assertEqual(query.to_sql(), EXPECTED[name]["select_raw_only"])
                self.assertEqual(len(query._columns), 1)

    def test_select_raw_accepts_tuple_bindings(self):
        query = qb(PostgresGrammar, "lexemes").select_raw("? AS a, ? AS b", (1, 2))

        self.assertEqual(query.to_qmark(), 'SELECT ? AS a, ? AS b FROM "lexemes"')
        self.assertEqual(list(query.get_bindings()), [1, 2])


class TestJoinSubGrammar(unittest.TestCase):
    def test_join_sub_with_builder_uses_its_bindings(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                subquery = (
                    qb(grammar, "memories").select("lexeme_id").where("memories.skill_id", 3).group_by("lexeme_id")
                )
                query = (
                    qb(grammar, "lexemes")
                    .join_sub(subquery, "due", "due.lexeme_id", "=", "lexemes.id")
                    .where("lexemes.language", "fr")
                )

                self.assertEqual(query.to_qmark(), EXPECTED[name]["join_sub"])
                self.assertEqual(list(query.get_bindings()), [3, "fr"])
                self.assertEqual(query.to_sql(), EXPECTED[name]["join_sub_sql"])

    def test_left_join_sub_with_raw_sql_and_bindings(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = qb(grammar, "lexemes").left_join_sub(
                    DUE, "due", "due.lexeme_id", "=", "lexemes.id", ["2026-01-01", "2026-01-31"]
                )

                self.assertEqual(query.to_qmark(), EXPECTED[name]["left_join_sub"])
                self.assertEqual(list(query.get_bindings()), ["2026-01-01", "2026-01-31"])

    def test_join_sub_rejects_bindings_with_a_builder(self):
        subquery = qb(PostgresGrammar, "memories").select("lexeme_id")

        with self.assertRaises(TypeError):
            qb(PostgresGrammar, "lexemes").join_sub(subquery, "due", "due.lexeme_id", "=", "lexemes.id", [1])

    def test_join_sub_rejects_other_query_types(self):
        with self.assertRaises(TypeError):
            qb(PostgresGrammar, "lexemes").join_sub(42, "due", "due.lexeme_id", "=", "lexemes.id")

    def test_join_sub_subquery_bindings_precede_on_value_bindings(self):
        query = qb(PostgresGrammar, "lexemes").left_join_sub(
            "SELECT lexeme_id FROM memories WHERE skill_id = ?", "due", "due.lexeme_id", "=", "lexemes.id", [7]
        )
        query._joins[0].on_value("due.lexeme_id", ">", 0)

        self.assertEqual(
            query.to_qmark(),
            'SELECT * FROM "lexemes" LEFT JOIN (SELECT lexeme_id FROM memories WHERE skill_id = ?) AS "due" '
            'ON "due"."lexeme_id" = "lexemes"."id" AND "due"."lexeme_id" > ?',
        )
        self.assertEqual(list(query.get_bindings()), [7, 0])


class TestListingQueryBindingOrder(unittest.TestCase):
    def test_select_join_where_bindings_follow_placeholder_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                query = listing_query(grammar)
                sql = query.to_qmark()

                self.assertEqual(sql, EXPECTED[name]["combined"])
                self.assertEqual(list(query.get_bindings()), ["ocr", "2026-01-01", "fr", "2026-01-01", "2026-01-31"])
                self.assertEqual(sql.count("?"), len(query.get_bindings()))

    def test_to_sql_inlines_builder_values_and_keeps_raw_placeholders_in_order(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                self.assertEqual(listing_query(grammar).to_sql(), EXPECTED[name]["combined_sql"])

    def test_order_by_subquery_bindings_come_after_where_bindings(self):
        ranking = qb(PostgresGrammar, "memories").select("due_date").where("memories.skill_id", 9).limit(1)
        query = (
            qb(PostgresGrammar, "lexemes")
            .select_raw("? AS marker", ["m"])
            .left_join_sub(
                "SELECT lexeme_id FROM memories WHERE skill_id = ?", "due", "due.lexeme_id", "=", "lexemes.id", [5]
            )
            .where("lexemes.language", "fr")
            .order_by(ranking)
        )

        query.to_qmark()

        self.assertEqual(list(query.get_bindings()), ["m", 5, "fr", 9])


class TestAggregateGrammar(unittest.IsolatedAsyncioTestCase):
    def postgres_builder(self, table):
        connection = Mock()
        connection.select_one = AsyncMock(return_value={"aggregate": 3})
        query = QueryBuilder(connection=connection, grammar=PostgresGrammar, processor=None)
        query._table = table
        return query

    async def test_count_drops_columns_and_order_by_but_keeps_join_and_where_bindings(self):
        query = self.postgres_builder("lexemes")
        query.select("lexemes.*").select_raw(OCR, ["ocr"]).left_join_sub(
            DUE, "due", "due.lexeme_id", "=", "lexemes.id", ["2026-01-01", "2026-01-31"]
        ).where("lexemes.language", "fr").order_by("lexemes.text")

        self.assertEqual(await query.count(), 3)

        sql, bindings = query.connection.select_one.call_args[0]
        self.assertEqual(
            sql,
            'SELECT COUNT(*) FROM "lexemes" LEFT JOIN (' + DUE + ') AS "due" ON "due"."lexeme_id" = "lexemes"."id" '
            'WHERE "lexemes"."language" = ?',
        )
        self.assertEqual(bindings, ["2026-01-01", "2026-01-31", "fr"])

    async def test_count_leaves_the_builder_unchanged(self):
        query = self.postgres_builder("lexemes")
        query.select("lexemes.id").select_raw(OCR, ["ocr"]).order_by("lexemes.text")
        before = query.to_qmark()

        await query.count()

        self.assertEqual(query.to_qmark(), before)
        self.assertEqual(list(query.get_bindings()), ["ocr"])

    async def test_grouped_aggregate_keeps_columns_and_order_by(self):
        query = self.postgres_builder("payments")
        query.select("user_id").group_by("user_id").order_by("user_id")

        await query.min("salary")

        sql, _ = query.connection.select_one.call_args[0]
        self.assertEqual(
            sql,
            'SELECT "payments"."user_id", MIN("payments"."salary") AS salary FROM "payments" '
            'GROUP BY "payments"."user_id" ORDER BY "user_id" ASC',
        )


if __name__ == "__main__":
    unittest.main()

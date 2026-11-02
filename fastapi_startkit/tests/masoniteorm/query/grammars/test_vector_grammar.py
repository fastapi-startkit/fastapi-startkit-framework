import unittest

from fastapi_startkit.masoniteorm.models.builder import QueryBuilder
from fastapi_startkit.masoniteorm.query.grammars.MSSQLGrammar import MSSQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.MySQLGrammar import MySQLGrammar
from fastapi_startkit.masoniteorm.query.grammars.PostgresGrammar import PostgresGrammar
from fastapi_startkit.masoniteorm.query.grammars.SQLiteGrammar import SQLiteGrammar

VECTOR = [0.1, 0.2, 0.3]
LITERAL = "[0.1, 0.2, 0.3]"


def qb(grammar=PostgresGrammar):
    q = QueryBuilder(connection=None, grammar=grammar, processor=None)
    q._table = "documents"
    return q


class TestVectorGrammar(unittest.TestCase):
    def test_select_vector_distance_adds_the_distance_after_all_columns(self):
        q = qb().select_vector_distance("embedding", VECTOR)

        self.assertEqual(
            q.to_qmark(),
            'SELECT "documents".*, ("documents"."embedding" <=> ?) AS "embedding_distance" FROM "documents"',
        )
        self.assertEqual(list(q.get_bindings()), [LITERAL])

    def test_select_vector_distance_accepts_an_alias_and_a_qualified_column(self):
        q = qb().select("id").select_vector_distance("documents.embedding", VECTOR, as_="distance")

        self.assertEqual(
            q.to_qmark(), 'SELECT "documents"."id", ("documents"."embedding" <=> ?) AS "distance" FROM "documents"'
        )

    def test_where_vector_distance_less_than_binds_vector_and_distance(self):
        q = qb().where("team_id", 7).where_vector_distance_less_than("embedding", VECTOR, 0.3)

        self.assertEqual(
            q.to_qmark(),
            'SELECT * FROM "documents" WHERE "documents"."team_id" = ? AND ("documents"."embedding" <=> ?) <= ?',
        )
        self.assertEqual(list(q.get_bindings()), [7, LITERAL, 0.3])

    def test_or_where_vector_distance_less_than(self):
        q = qb().where("id", 1).or_where_vector_distance_less_than("embedding", VECTOR, 0.2)

        self.assertEqual(
            q.to_qmark(), 'SELECT * FROM "documents" WHERE "documents"."id" = ? OR ("documents"."embedding" <=> ?) <= ?'
        )
        self.assertEqual(list(q.get_bindings()), [1, LITERAL, 0.2])

    def test_order_by_vector_distance_follows_other_orders(self):
        q = qb().order_by("title").order_by_vector_distance("embedding", VECTOR)

        self.assertEqual(
            q.to_qmark(), 'SELECT * FROM "documents" ORDER BY "title" ASC, ("documents"."embedding" <=> ?) ASC'
        )
        self.assertEqual(list(q.get_bindings()), [LITERAL])

    def test_raw_order_by_after_another_order_is_comma_separated(self):
        q = qb().order_by("title").order_by_raw("id DESC")

        self.assertEqual(q.to_qmark(), 'SELECT * FROM "documents" ORDER BY "title" ASC, id DESC')

    def test_where_vector_similar_to_filters_by_distance_and_orders(self):
        q = qb().where_vector_similar_to("embedding", VECTOR, min_similarity=0.4).limit(10)

        self.assertEqual(
            q.to_qmark(),
            'SELECT * FROM "documents" WHERE ("documents"."embedding" <=> ?) <= ? '
            'ORDER BY ("documents"."embedding" <=> ?) ASC LIMIT 10',
        )
        bindings = list(q.get_bindings())
        self.assertEqual(bindings[0], LITERAL)
        self.assertEqual(bindings[2], LITERAL)
        self.assertAlmostEqual(bindings[1], 0.6)

    def test_where_vector_similar_to_can_skip_ordering(self):
        q = qb().where_vector_similar_to("embedding", VECTOR, order=False)

        self.assertEqual(q.to_qmark(), 'SELECT * FROM "documents" WHERE ("documents"."embedding" <=> ?) <= ?')
        self.assertAlmostEqual(list(q.get_bindings())[1], 0.4)

    def test_bindings_follow_sql_order(self):
        q = (
            qb()
            .select("id")
            .select_vector_distance("embedding", [1, 0])
            .where_vector_distance_less_than("embedding", [0, 1], 0.5)
            .order_by_vector_distance("embedding", [1, 1])
        )
        q.to_qmark()

        self.assertEqual(list(q.get_bindings()), ["[1.0, 0.0]", "[0.0, 1.0]", 0.5, "[1.0, 1.0]"])

    def test_vectors_accept_any_numeric_sequence(self):
        q = qb().order_by_vector_distance("embedding", (1, 2.5))
        q.to_qmark()

        self.assertEqual(list(q.get_bindings()), ["[1.0, 2.5]"])

    def test_text_vectors_are_rejected(self):
        with self.assertRaisesRegex(TypeError, "to_embeddings"):
            qb().where_vector_similar_to("embedding", "best wineries")

    def test_vector_columns_use_the_query_alias(self):
        q = qb().table("documents", "d").order_by_vector_distance("embedding", VECTOR)

        self.assertEqual(q.to_qmark(), 'SELECT * FROM "documents" AS "d" ORDER BY ("d"."embedding" <=> ?) ASC')

    def test_vector_columns_keep_a_schema_qualified_table(self):
        q = qb().table("search.documents").order_by_vector_distance("embedding", VECTOR)

        self.assertIn('("search"."documents"."embedding" <=> ?) ASC', q.to_qmark())

    def test_vector_identifiers_escape_embedded_quotes(self):
        injected = 'emb" <=> ?) AS x FROM pg_shadow --'
        q = (
            qb()
            .select_vector_distance(injected, VECTOR, as_=injected)
            .where_vector_distance_less_than(injected, VECTOR, 0.5)
        )

        self.assertEqual(
            q.to_qmark(),
            'SELECT "documents".*, ("documents"."emb"" <=> ?) AS x FROM pg_shadow --" <=> ?) '
            'AS "emb"" <=> ?) AS x FROM pg_shadow --" FROM "documents" '
            'WHERE ("documents"."emb"" <=> ?) AS x FROM pg_shadow --" <=> ?) <= ?',
        )

    def test_vector_queries_require_postgres(self):
        for grammar in (SQLiteGrammar, MySQLGrammar, MSSQLGrammar):
            with self.subTest(grammar=grammar.__name__):
                with self.assertRaisesRegex(ValueError, "does not support vector queries"):
                    qb(grammar).where_vector_similar_to("embedding", VECTOR)

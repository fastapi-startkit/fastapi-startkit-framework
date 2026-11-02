import pytest

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


def test_select_vector_distance_adds_the_distance_after_all_columns():
    q = qb().select_vector_distance("embedding", VECTOR)

    assert (
        q.to_qmark() == 'SELECT "documents".*, ("documents"."embedding" <=> ?) AS "embedding_distance" FROM "documents"'
    )
    assert list(q.get_bindings()) == [LITERAL]


def test_select_vector_distance_accepts_an_alias_and_a_qualified_column():
    q = qb().select("id").select_vector_distance("documents.embedding", VECTOR, as_="distance")

    assert q.to_qmark() == 'SELECT "documents"."id", ("documents"."embedding" <=> ?) AS "distance" FROM "documents"'


def test_where_vector_distance_less_than_binds_vector_and_distance():
    q = qb().where("team_id", 7).where_vector_distance_less_than("embedding", VECTOR, 0.3)

    assert (
        q.to_qmark()
        == 'SELECT * FROM "documents" WHERE "documents"."team_id" = ? AND ("documents"."embedding" <=> ?) <= ?'
    )
    assert list(q.get_bindings()) == [7, LITERAL, 0.3]


def test_or_where_vector_distance_less_than():
    q = qb().where("id", 1).or_where_vector_distance_less_than("embedding", VECTOR, 0.2)

    assert (
        q.to_qmark() == 'SELECT * FROM "documents" WHERE "documents"."id" = ? OR ("documents"."embedding" <=> ?) <= ?'
    )
    assert list(q.get_bindings()) == [1, LITERAL, 0.2]


def test_order_by_vector_distance_follows_other_orders():
    q = qb().order_by("title").order_by_vector_distance("embedding", VECTOR)

    assert q.to_qmark() == 'SELECT * FROM "documents" ORDER BY "title" ASC, ("documents"."embedding" <=> ?) ASC'
    assert list(q.get_bindings()) == [LITERAL]


def test_raw_order_by_after_another_order_is_comma_separated():
    q = qb().order_by("title").order_by_raw("id DESC")

    assert q.to_qmark() == 'SELECT * FROM "documents" ORDER BY "title" ASC, id DESC'


def test_where_vector_similar_to_filters_by_distance_and_orders():
    q = qb().where_vector_similar_to("embedding", VECTOR, min_similarity=0.4).limit(10)

    assert q.to_qmark() == (
        'SELECT * FROM "documents" WHERE ("documents"."embedding" <=> ?) <= ? ORDER BY ("documents"."embedding" <=> ?) ASC LIMIT 10'
    )
    bindings = list(q.get_bindings())
    assert bindings[0] == bindings[2] == LITERAL
    assert bindings[1] == pytest.approx(0.6)


def test_where_vector_similar_to_can_skip_ordering():
    q = qb().where_vector_similar_to("embedding", VECTOR, order=False)

    assert q.to_qmark() == 'SELECT * FROM "documents" WHERE ("documents"."embedding" <=> ?) <= ?'
    assert list(q.get_bindings())[1] == pytest.approx(0.4)


def test_bindings_follow_sql_order():
    q = (
        qb()
        .select("id")
        .select_vector_distance("embedding", [1, 0])
        .where_vector_distance_less_than("embedding", [0, 1], 0.5)
        .order_by_vector_distance("embedding", [1, 1])
    )
    q.to_qmark()

    assert list(q.get_bindings()) == ["[1.0, 0.0]", "[0.0, 1.0]", 0.5, "[1.0, 1.0]"]


def test_vectors_accept_any_numeric_sequence():
    q = qb().order_by_vector_distance("embedding", (1, 2.5))
    q.to_qmark()

    assert list(q.get_bindings()) == ["[1.0, 2.5]"]


def test_text_vectors_are_rejected():
    with pytest.raises(TypeError, match="to_embeddings"):
        qb().where_vector_similar_to("embedding", "best wineries")


def test_vector_columns_use_the_query_alias():
    q = qb().table("documents", "d").order_by_vector_distance("embedding", VECTOR)

    assert q.to_qmark() == 'SELECT * FROM "documents" AS "d" ORDER BY ("d"."embedding" <=> ?) ASC'


def test_vector_columns_keep_a_schema_qualified_table():
    q = qb().table("search.documents").order_by_vector_distance("embedding", VECTOR)

    assert '("search"."documents"."embedding" <=> ?) ASC' in q.to_qmark()


def test_vector_identifiers_escape_embedded_quotes():
    injected = 'emb" <=> ?) AS x FROM pg_shadow --'
    q = (
        qb()
        .select_vector_distance(injected, VECTOR, as_=injected)
        .where_vector_distance_less_than(injected, VECTOR, 0.5)
    )

    assert q.to_qmark() == (
        'SELECT "documents".*, ("documents"."emb"" <=> ?) AS x FROM pg_shadow --" <=> ?) '
        'AS "emb"" <=> ?) AS x FROM pg_shadow --" FROM "documents" '
        'WHERE ("documents"."emb"" <=> ?) AS x FROM pg_shadow --" <=> ?) <= ?'
    )


@pytest.mark.parametrize("grammar", [SQLiteGrammar, MySQLGrammar, MSSQLGrammar])
def test_vector_queries_require_postgres(grammar):
    with pytest.raises(ValueError, match="does not support vector queries"):
        qb(grammar).where_vector_similar_to("embedding", VECTOR)

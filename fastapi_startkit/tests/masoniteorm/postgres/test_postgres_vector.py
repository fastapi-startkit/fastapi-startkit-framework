from fastapi_startkit.masoniteorm import Model

from .fixtures.db import schema
from .test_case import TestCase


class VecDocument(Model):
    __table__ = "vec_documents"
    __timestamps__ = None
    __fillable__ = ["title", "embedding"]
    id: int
    title: str
    embedding: list[float]


class TestPostgresVector(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await schema.ensure_vector_extension_exists()
        await schema.drop_table_if_exists("vec_documents")
        async with await schema.create("vec_documents") as table:
            table.increments("id")
            table.string("title")
            table.vector("embedding", dimensions=3).index()
        await VecDocument.create({"title": "wine", "embedding": [1.0, 0.0, 0.0]})
        await VecDocument.create({"title": "vineyard", "embedding": [0.9, 0.1, 0.0]})
        await VecDocument.create({"title": "framework", "embedding": [0.0, 0.0, 1.0]})

    async def asyncTearDown(self):
        await schema.drop_table_if_exists("vec_documents")
        await super().asyncTearDown()

    async def test_vectors_round_trip_through_the_model(self):
        document = await VecDocument.where("title", "wine").first()

        self.assertEqual(document.embedding, [1.0, 0.0, 0.0])

    async def test_where_vector_similar_to_returns_closest_first(self):
        documents = await VecDocument.where_vector_similar_to("embedding", [1.0, 0.05, 0.0], min_similarity=0.5).get()

        self.assertEqual([document.title for document in documents], ["wine", "vineyard"])

    async def test_select_vector_distance(self):
        documents = (
            await VecDocument.select("title")
            .select_vector_distance("embedding", [0.0, 0.0, 1.0])
            .order_by_vector_distance("embedding", [0.0, 0.0, 1.0])
            .get()
        )

        self.assertEqual(documents[0].title, "framework")
        self.assertAlmostEqual(documents[0].embedding_distance, 0.0)
        self.assertAlmostEqual(documents[2].embedding_distance, 1.0)

    async def test_where_vector_distance_less_than(self):
        documents = await VecDocument.where_vector_distance_less_than("embedding", [0.0, 0.0, 1.0], 0.1).get()

        self.assertEqual([document.title for document in documents], ["framework"])

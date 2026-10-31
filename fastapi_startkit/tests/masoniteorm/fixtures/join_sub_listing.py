from datetime import date

from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.models.builder import QueryBuilder

WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2026, 1, 31)
DUE_FLOOR = date(2026, 1, 4)

VERIFICATION = (
    "COALESCE((SELECT v.status FROM verifications v WHERE v.lexeme_id = lexemes.id AND v.type = ?), "
    "'unverified') AS verification"
)


class Lexeme(Model):
    __table__ = "lexemes"
    __timestamps__ = False
    id: int
    text: str
    language: str


class Memory(Model):
    __table__ = "memories"
    __timestamps__ = False
    id: int
    lexeme_id: int


class Verification(Model):
    __table__ = "verifications"
    __timestamps__ = False
    id: int
    lexeme_id: int


async def create_listing_tables(schema) -> None:
    async with await schema.create("lexemes") as table:
        table.id()
        table.string("text")
        table.string("language")
    async with await schema.create("memories") as table:
        table.id()
        table.integer("lexeme_id")
        table.date("due_date")
        table.integer("skill_id").nullable()
    async with await schema.create("verifications") as table:
        table.id()
        table.integer("lexeme_id")
        table.string("type")
        table.string("status")


async def seed_listing() -> None:
    await Lexeme.query().insert(
        [
            {"id": 1, "text": "avoir", "language": "fr"},
            {"id": 2, "text": "boire", "language": "fr"},
            {"id": 3, "text": "chat", "language": "fr"},
            {"id": 4, "text": "dog", "language": "en"},
            {"id": 5, "text": "etre", "language": "fr"},
        ]
    )
    await Memory.query().insert(
        [
            {"id": 1, "lexeme_id": 1, "due_date": date(2026, 1, 5), "skill_id": None},
            {"id": 2, "lexeme_id": 1, "due_date": date(2026, 1, 3), "skill_id": None},
            {"id": 3, "lexeme_id": 2, "due_date": date(2026, 1, 10), "skill_id": None},
            {"id": 4, "lexeme_id": 2, "due_date": date(2026, 1, 2), "skill_id": 4},
            {"id": 5, "lexeme_id": 3, "due_date": date(2026, 1, 3), "skill_id": None},
            {"id": 6, "lexeme_id": 4, "due_date": date(2026, 1, 4), "skill_id": None},
            {"id": 7, "lexeme_id": 5, "due_date": date(2026, 3, 1), "skill_id": None},
        ]
    )
    await Verification.query().insert(
        [
            {"id": 1, "lexeme_id": 1, "type": "meaning", "status": "verified"},
            {"id": 2, "lexeme_id": 1, "type": "ocr", "status": "pending"},
            {"id": 3, "lexeme_id": 3, "type": "meaning", "status": "rejected"},
        ]
    )


def due_subquery(due_day_expression: str) -> QueryBuilder[Memory]:
    return (
        Memory.query()
        .select_raw(f"memories.lexeme_id, {due_day_expression} AS due_day", [DUE_FLOOR])
        .select_raw("MIN(memories.due_date) AS oldest_due, COUNT(*) AS learners")
        .between("memories.due_date", WINDOW_START, WINDOW_END)
        .where_null("memories.skill_id")
        .group_by("memories.lexeme_id")
    )


def due_subquery_sql(due_day_expression: str) -> str:
    return (
        f"SELECT memories.lexeme_id, {due_day_expression} AS due_day, MIN(memories.due_date) AS oldest_due, "
        "COUNT(*) AS learners FROM memories WHERE memories.due_date BETWEEN ? AND ? "
        "AND memories.skill_id IS NULL GROUP BY memories.lexeme_id"
    )


def listing_query(due: "QueryBuilder[Memory] | str", bindings: tuple = ()) -> QueryBuilder[Lexeme]:
    return (
        Lexeme.query()
        .select("lexemes.*", "due.due_day as due_date", "due.learners as learners")
        .select_raw(VERIFICATION, ["meaning"])
        .left_join_sub(due, "due", "due.lexeme_id", "=", "lexemes.id", bindings)
        .where("lexemes.language", "fr")
        .where_raw("due.due_day BETWEEN ? AND ?", [WINDOW_START, WINDOW_END])
        .order_by("due.due_day")
        .order_by("lexemes.text")
        .order_by("lexemes.id")
    )


def listing_rows(lexemes) -> list[tuple]:
    return [
        (
            row["id"],
            row["text"],
            str(row["due_date"])[:10],
            int(row["learners"]),
            row["verification"],
        )
        for row in (lexeme.serialize() for lexeme in lexemes)
    ]

from unittest.mock import patch

import pytest

from fastapi_startkit.masoniteorm import HasMany, HasOne, Model, relationship
from fastapi_startkit.masoniteorm.connections.connection import Connection

from ..test_case import TestCase


class OfManyStatus(Model):
    __table__ = "of_many_statuses"
    __timestamps__ = False


class OfManyUser(Model):
    __table__ = "of_many_users"
    __timestamps__ = False

    statuses = HasMany["OfManyStatus"](local_key="id", foreign_key="user_id")

    @relationship
    def due_date(self) -> HasOne["OfManyStatus"]:
        return self.statuses.latest_of_many()

    @relationship
    def first_status(self) -> HasOne["OfManyStatus"]:
        return self.statuses.oldest_of_many()

    @relationship
    def most_urgent(self) -> HasOne["OfManyStatus"]:
        return self.statuses.of_many("priority", "max")

    @relationship
    def least_urgent(self) -> HasOne["OfManyStatus"]:
        return self.statuses.of_many("priority", "min")

    @relationship
    @classmethod
    def latest_status(cls) -> HasOne["OfManyStatus"]:
        return cls.statuses.latest_of_many()


class TestHasOneOfMany(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("of_many_users") as table:
            table.id()
            table.string("name")
        async with await self.schema.create_table_if_not_exists("of_many_statuses") as table:
            table.id()
            table.integer("user_id")
            table.string("name")
            table.integer("priority")
            table.timestamp("created_at")

        self.alice = await OfManyUser.create({"name": "Alice"})
        self.bob = await OfManyUser.create({"name": "Bob"})
        self.carol = await OfManyUser.create({"name": "Carol"})

        await self.status(self.alice, "opened", 2, "2026-01-01 00:00:00")
        await self.status(self.alice, "done", 1, "2026-03-01 00:00:00")
        await self.status(self.alice, "review", 3, "2026-02-01 00:00:00")
        await self.status(self.bob, "tied-first", 5, "2026-05-01 00:00:00")
        await self.status(self.bob, "tied-second", 5, "2026-05-01 00:00:00")

    async def status(self, user, name, priority, created_at):
        await OfManyStatus.create({"user_id": user.id, "name": name, "priority": priority, "created_at": created_at})

    async def names_by_user(self, relation):
        users = await OfManyUser.with_(relation).order_by("id").get()
        return {user.name: getattr(getattr(user, relation), "name", None) for user in users}

    async def test_eager_latest_of_many_picks_latest_row_per_parent_with_pk_tie_break(self):
        self.assertEqual(
            await self.names_by_user("due_date"),
            {"Alice": "done", "Bob": "tied-second", "Carol": None},
        )

    async def test_classmethod_form_resolves_the_same_relation(self):
        self.assertEqual(
            await self.names_by_user("latest_status"),
            {"Alice": "done", "Bob": "tied-second", "Carol": None},
        )

    async def test_eager_oldest_of_many_picks_oldest_row_per_parent_with_pk_tie_break(self):
        self.assertEqual(
            await self.names_by_user("first_status"),
            {"Alice": "opened", "Bob": "tied-first", "Carol": None},
        )

    async def test_of_many_max_and_min_on_a_custom_column(self):
        self.assertEqual(
            await self.names_by_user("most_urgent"),
            {"Alice": "review", "Bob": "tied-second", "Carol": None},
        )
        self.assertEqual(
            await self.names_by_user("least_urgent"),
            {"Alice": "done", "Bob": "tied-first", "Carol": None},
        )

    async def test_eager_load_selects_one_row_per_parent_in_a_single_query(self):
        with patch.object(Connection, "select", autospec=True, side_effect=Connection.select) as select:
            users = await OfManyUser.with_("due_date").get()

        self.assertEqual(select.call_count, 2)
        rows = await OfManyUser.due_date.where_in("of_many_statuses.user_id", users.pluck("id")).get()
        self.assertEqual(sorted(row.name for row in rows), ["done", "tied-second"])

    async def test_lazy_load_on_a_single_model(self):
        alice = await OfManyUser.find(self.alice.id)
        carol = await OfManyUser.find(self.carol.id)

        await alice.load("due_date")
        await carol.load("due_date")

        self.assertEqual(alice.due_date.name, "done")
        self.assertIsNone(carol.due_date)

    async def test_lazy_load_on_a_collection(self):
        users = await OfManyUser.order_by("id").get()
        await users.load("first_status")

        self.assertEqual([getattr(user.first_status, "name", None) for user in users], ["opened", "tied-first", None])

    async def test_where_has_constrains_only_the_selected_row(self):
        latest_done = await OfManyUser.where_has("due_date", lambda q: q.where("name", "done")).get()
        any_review = await OfManyUser.where_has("statuses", lambda q: q.where("name", "review")).get()
        latest_review = await OfManyUser.where_has("due_date", lambda q: q.where("name", "review")).get()

        self.assertEqual(latest_done.pluck("name").all(), ["Alice"])
        self.assertEqual(any_review.pluck("name").all(), ["Alice"])
        self.assertTrue(latest_review.is_empty())

    async def test_where_has_without_callback_matches_parents_with_children(self):
        users = await OfManyUser.where_has("due_date").order_by("id").get()

        self.assertEqual(users.pluck("name").all(), ["Alice", "Bob"])

    async def test_has_many_is_unchanged(self):
        user = await OfManyUser.with_("statuses").find(self.alice.id)

        self.assertEqual(len(user.statuses), 3)

    async def test_unknown_aggregate_is_rejected(self):
        with pytest.raises(ValueError, match="aggregate"):
            OfManyUser.statuses.of_many("priority", "avg")

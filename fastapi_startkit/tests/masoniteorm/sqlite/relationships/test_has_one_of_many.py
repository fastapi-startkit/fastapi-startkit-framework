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
            table.timestamp("created_at", nullable=True)

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
            OfManyUser.statuses.of_many("priority", "avg")  # pyright: ignore[reportArgumentType]

    async def test_related_model_resolves_through_the_parent_relation(self):
        self.assertIs(OfManyUser.due_date.related_model(), OfManyStatus)

    async def test_returning_an_existing_relation_is_rejected_and_leaves_it_intact(self):
        class AliasedUser(Model):
            __table__ = "of_many_users"
            __timestamps__ = False

            statuses = HasMany["OfManyStatus"](local_key="id", foreign_key="user_id")

            @relationship
            def items(self) -> HasMany["OfManyStatus"]:
                return self.statuses

            @relationship
            def done_statuses(self) -> HasMany["OfManyStatus"]:
                return self.statuses.where("name", "done")

        with pytest.raises(TypeError, match="must return a new relationship"):
            AliasedUser.items
        with pytest.raises(TypeError, match="must return a new relationship"):
            AliasedUser.done_statuses

        user = await AliasedUser.with_("statuses").find(self.alice.id)
        self.assertEqual(len(user.statuses), 3)

    async def test_unnamed_has_many_without_foreign_key_is_rejected(self):
        with pytest.raises(TypeError, match="explicit foreign_key"):
            HasMany["OfManyStatus"]().latest_of_many()


class OfManyEvent(Model):
    __table__ = "of_many_events"
    __timestamps__ = False


class OfManyTicket(Model):
    __table__ = "of_many_tickets"
    __primary_key__ = "ticket_id"
    __timestamps__ = False


class OfManyAccount(Model):
    __table__ = "of_many_accounts"
    __timestamps__ = False

    events = HasMany["OfManyEvent"](local_key="id", foreign_key="account_id")
    tickets = HasMany["OfManyTicket"](local_key="id", foreign_key="account_id")

    @relationship
    def latest_event(self) -> HasOne["OfManyEvent"]:
        return self.events.latest_of_many()

    @relationship
    def oldest_event(self) -> HasOne["OfManyEvent"]:
        return self.events.oldest_of_many()

    @relationship
    def newest_ticket(self) -> HasOne["OfManyTicket"]:
        return self.tickets.of_many()

    @relationship
    def first_ticket(self) -> HasOne["OfManyTicket"]:
        return self.tickets.of_many(aggregate="min")


class OfManyPremiumAccount(OfManyAccount):
    pass


class OfManyNode(Model):
    __table__ = "of_many_nodes"
    __timestamps__ = False

    children = HasMany["OfManyNode"](local_key="id", foreign_key="parent_id")

    @relationship
    def newest_child(self) -> HasOne["OfManyNode"]:
        return self.children.of_many()


class TestHasOneOfManyEdgeCases(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("of_many_accounts") as table:
            table.id()
            table.string("name")
        async with await self.schema.create_table_if_not_exists("of_many_events") as table:
            table.id()
            table.integer("account_id")
            table.string("name")
            table.timestamp("created_at", nullable=True)
        async with await self.schema.create_table_if_not_exists("of_many_tickets") as table:
            table.increments("ticket_id")
            table.integer("account_id")
            table.string("name")
        async with await self.schema.create_table_if_not_exists("of_many_nodes") as table:
            table.id()
            table.string("name")
            table.integer("parent_id").nullable()

        self.acme = await OfManyAccount.create({"name": "Acme"})
        self.blank = await OfManyAccount.create({"name": "Blank"})
        events = [("dated-old", "2026-01-01 00:00:00"), ("null-ts", None), ("dated-new", "2026-02-01 00:00:00")]
        for name, created_at in events:
            await OfManyEvent.create({"account_id": self.acme.id, "name": name, "created_at": created_at})
        await OfManyEvent.create({"account_id": self.blank.id, "name": "only-null", "created_at": None})
        for name in ["ticket-1", "ticket-2"]:
            await OfManyTicket.create({"account_id": self.acme.id, "name": name})

        root = await OfManyNode.create({"name": "root"})
        await OfManyNode.create({"name": "child-1", "parent_id": root.id})
        await OfManyNode.create({"name": "child-2", "parent_id": root.id})

    async def names_by_parent(self, model, relation):
        parents = await model.with_(relation).order_by("id").get()
        return {parent.name: getattr(getattr(parent, relation), "name", None) for parent in parents}

    async def test_null_columns_are_ignored_like_max_and_min(self):
        self.assertEqual(
            await self.names_by_parent(OfManyAccount, "latest_event"), {"Acme": "dated-new", "Blank": None}
        )
        self.assertEqual(
            await self.names_by_parent(OfManyAccount, "oldest_event"), {"Acme": "dated-old", "Blank": None}
        )

    async def test_of_many_defaults_to_the_related_primary_key(self):
        self.assertEqual(
            await self.names_by_parent(OfManyAccount, "newest_ticket"), {"Acme": "ticket-2", "Blank": None}
        )
        self.assertEqual(await self.names_by_parent(OfManyAccount, "first_ticket"), {"Acme": "ticket-1", "Blank": None})

    async def test_primary_key_column_is_ordered_once_without_a_null_filter(self):
        sql = OfManyAccount.newest_ticket.to_sql()

        self.assertIn('ORDER BY "of_many_tickets_of_many"."ticket_id" DESC LIMIT 1', sql)
        self.assertEqual(sql.count("ORDER BY"), 1)
        self.assertNotIn("IS NOT NULL", sql)

    async def test_subclass_of_the_owner_resolves_its_own_relation(self):
        self.assertEqual(
            await self.names_by_parent(OfManyPremiumAccount, "latest_event"), {"Acme": "dated-new", "Blank": None}
        )
        self.assertIsNot(OfManyPremiumAccount.latest_event, OfManyAccount.latest_event)

    async def test_self_referencing_relation_eager_and_where_has(self):
        nodes = await OfManyNode.with_("newest_child").order_by("id").get()
        with_child_two = await OfManyNode.where_has("newest_child", lambda q: q.where("name", "child-2")).get()
        with_child_one = await OfManyNode.where_has("newest_child", lambda q: q.where("name", "child-1")).get()

        self.assertEqual(
            {node.name: getattr(node.newest_child, "name", None) for node in nodes},
            {"root": "child-2", "child-1": None, "child-2": None},
        )
        self.assertEqual(with_child_two.pluck("name").all(), ["root"])
        self.assertTrue(with_child_one.is_empty())

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, Model

from ..test_case import TestCase


class Member(Model):
    __table__ = "members"
    __timestamps__ = False

    friends: "Member" = BelongsToMany["Member"](
        local_foreign_key="member_id",
        other_foreign_key="friend_id",
        local_owner_key="id",
        other_owner_key="id",
        table="friendships",
    )
    children: "Member" = HasMany["Member"](local_key="id", foreign_key="parent_id")
    parent: "Member" = BelongsTo["Member"](local_key="parent_id", foreign_key="id")


class TestSelfRelationWhereHas(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("members") as table:
            table.id()
            table.string("name")
            table.integer("parent_id").nullable()
        async with await self.schema.create_table_if_not_exists("friendships") as table:
            table.id()
            table.integer("member_id")
            table.integer("friend_id")

        self.alice = await Member.create({"name": "Alice"})
        self.bob = await Member.create({"name": "Bob", "parent_id": self.alice.id})
        self.carol = await Member.create({"name": "Carol", "parent_id": self.bob.id})
        self.dave = await Member.create({"name": "Dave"})
        await Member.friends.attach(self.alice, self.bob)
        await Member.friends.attach(self.carol, self.dave)

    async def names(self, query):
        return sorted(member.name for member in await query.get())

    async def test_where_has_friends_with_callback(self):
        query = Member.where_has("friends", lambda q: q.where("name", "Bob"))
        self.assertEqual(await self.names(query), ["Alice"])

    async def test_where_has_friends_without_callback(self):
        self.assertEqual(await self.names(Member.where_has("friends")), ["Alice", "Carol"])

    async def test_or_where_has_friends_with_callback(self):
        query = Member.where("name", "Bob").or_where_has("friends", lambda q: q.where("name", "Dave"))
        self.assertEqual(await self.names(query), ["Bob", "Carol"])

    async def test_where_has_children_with_callback(self):
        query = Member.where_has("children", lambda q: q.where("name", "Carol"))
        self.assertEqual(await self.names(query), ["Bob"])

    async def test_where_has_children_without_callback(self):
        self.assertEqual(await self.names(Member.where_has("children")), ["Alice", "Bob"])

    async def test_or_where_has_children(self):
        query = Member.where("name", "Dave").or_where_has("children")
        self.assertEqual(await self.names(query), ["Alice", "Bob", "Dave"])

    async def test_where_has_parent_with_callback(self):
        query = Member.where_has("parent", lambda q: q.where("name", "Alice"))
        self.assertEqual(await self.names(query), ["Bob"])

    async def test_nested_where_has_children(self):
        query = Member.where_has("children", lambda q: q.where_has("children"))
        self.assertEqual(await self.names(query), ["Alice"])

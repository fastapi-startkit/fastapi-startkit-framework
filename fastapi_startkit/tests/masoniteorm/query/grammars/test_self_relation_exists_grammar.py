import unittest

from fastapi_startkit.masoniteorm import BelongsTo, BelongsToMany, HasMany, HasOne, Model
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

QUOTES = {"sqlite": '""', "mysql": "``", "postgres": '""', "mssql": "[]"}


def quote(dialect, *parts):
    left, right = QUOTES[dialect]
    return ".".join(f"{left}{part}{right}" for part in parts)


class FakeConnection:
    def __init__(self, grammar):
        self.grammar = grammar

    def query(self):
        return QueryBuilder(connection=self, grammar=self.grammar, processor=None)


class FakeManager:
    def __init__(self, grammar):
        self.grammar = grammar

    def connection(self, name=None):
        return FakeConnection(self.grammar)


class SelfMember(Model):
    __table__ = "members"

    friends: "SelfMember" = BelongsToMany["SelfMember"](
        local_foreign_key="member_id",
        other_foreign_key="friend_id",
        local_owner_key="id",
        other_owner_key="id",
        table="friendships",
    )
    children: "SelfMember" = HasMany["SelfMember"](local_key="id", foreign_key="parent_id")
    successor: "SelfMember" = HasOne["SelfMember"](local_key="id", foreign_key="predecessor_id")
    parent: "SelfMember" = BelongsTo["SelfMember"](local_key="parent_id", foreign_key="id")
    groups: "SelfGroup" = BelongsToMany["SelfGroup"](
        local_foreign_key="member_id",
        other_foreign_key="group_id",
        local_owner_key="id",
        other_owner_key="id",
        table="group_member",
    )
    posts: "SelfPost" = HasMany["SelfPost"](local_key="id", foreign_key="member_id")


class SelfGroup(Model):
    __table__ = "groups"


class SelfPost(Model):
    __table__ = "posts"


class TestSelfRelationExistsGrammar(unittest.TestCase):
    def setUp(self):
        self.previous_manager = Model.db_manager

    def tearDown(self):
        Model.db_manager = self.previous_manager

    def dialects(self):
        for name, grammar in GRAMMARS.items():
            with self.subTest(grammar=name):
                Model.db_manager = FakeManager(grammar)
                yield name

    def test_belongs_to_many_where_has_with_callback_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("friends", lambda q: q.where("name", "Bob")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} INNER JOIN {quote(d, 'friendships')} "
                f"ON {quote(d, 'members_self', 'id')} = {quote(d, 'friendships', 'friend_id')} "
                f"WHERE friendships.member_id = members.id AND {quote(d, 'members_self', 'name')} = 'Bob')",
            )

    def test_belongs_to_many_where_has_without_callback_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("friends").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} INNER JOIN {quote(d, 'friendships')} "
                f"ON {quote(d, 'members_self', 'id')} = {quote(d, 'friendships', 'friend_id')} "
                f"WHERE friendships.member_id = members.id)",
            )

    def test_belongs_to_many_or_where_has_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where("name", "Carol").or_where_has("friends", lambda q: q.where("name", "Bob")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE {quote(d, 'members', 'name')} = 'Carol' "
                f"OR EXISTS (SELECT * FROM {quote(d, 'members')} AS {quote(d, 'members_self')} "
                f"INNER JOIN {quote(d, 'friendships')} "
                f"ON {quote(d, 'members_self', 'id')} = {quote(d, 'friendships', 'friend_id')} "
                f"WHERE friendships.member_id = members.id AND {quote(d, 'members_self', 'name')} = 'Bob')",
            )

    def test_has_many_where_has_with_callback_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("children", lambda q: q.where("name", "Bob")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.parent_id = members.id "
                f"AND {quote(d, 'members_self', 'name')} = 'Bob')",
            )

    def test_has_many_where_has_without_callback_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("children").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.parent_id = members.id)",
            )

    def test_has_many_or_where_has_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where("name", "Carol").or_where_has("children").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE {quote(d, 'members', 'name')} = 'Carol' "
                f"OR EXISTS (SELECT * FROM {quote(d, 'members')} AS {quote(d, 'members_self')} "
                f"WHERE members_self.parent_id = members.id)",
            )

    def test_has_one_where_has_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("successor", lambda q: q.where("name", "Bob")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.predecessor_id = members.id "
                f"AND {quote(d, 'members_self', 'name')} = 'Bob')",
            )
            sql = SelfMember.where_has("successor").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.predecessor_id = members.id)",
            )

    def test_belongs_to_where_has_aliases_inner_table(self):
        for d in self.dialects():
            sql = SelfMember.where_has("parent", lambda q: q.where("name", "Bob")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.id = members.parent_id "
                f"AND {quote(d, 'members_self', 'name')} = 'Bob')",
            )
            sql = SelfMember.where_has("parent").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.id = members.parent_id)",
            )

    def test_nested_self_relation_gets_distinct_alias(self):
        for d in self.dialects():
            sql = SelfMember.where_has("children", lambda q: q.where_has("children")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'members')} "
                f"AS {quote(d, 'members_self')} WHERE members_self.parent_id = members.id "
                f"AND EXISTS (SELECT * FROM {quote(d, 'members')} AS {quote(d, 'members_self_self')} "
                f"WHERE members_self_self.parent_id = members_self.id))",
            )

    def test_non_self_belongs_to_many_is_unchanged(self):
        for d in self.dialects():
            sql = SelfMember.where_has("groups", lambda q: q.where("name", "Admins")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'groups')} "
                f"INNER JOIN {quote(d, 'group_member')} "
                f"ON {quote(d, 'groups', 'id')} = {quote(d, 'group_member', 'group_id')} "
                f"WHERE group_member.member_id = members.id AND {quote(d, 'groups', 'name')} = 'Admins')",
            )

    def test_non_self_has_many_is_unchanged(self):
        for d in self.dialects():
            sql = SelfMember.where_has("posts", lambda q: q.where("title", "Hi")).to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'posts')} "
                f"WHERE posts.member_id = members.id AND {quote(d, 'posts', 'title')} = 'Hi')",
            )
            sql = SelfMember.where_has("posts").to_sql()
            self.assertEqual(
                sql,
                f"SELECT * FROM {quote(d, 'members')} WHERE EXISTS (SELECT * FROM {quote(d, 'posts')} "
                f"WHERE posts.member_id = members.id)",
            )

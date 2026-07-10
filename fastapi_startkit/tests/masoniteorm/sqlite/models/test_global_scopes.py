from fastapi_startkit.masoniteorm.models.model import Model
from fastapi_startkit.masoniteorm import BelongsToMany
from ..test_case import TestCase


def only_published(query):
    return query.where("published", 1)


class ScopedPost(Model):
    __table__ = "scoped_posts"
    __timestamps__ = False
    __global_scopes__ = {"select": {"published": only_published}}

    title: str
    published: int


class DiscoveredComment(Model):
    __table__ = "discovered_comments"
    __timestamps__ = False

    body: str
    approved: int

    def scope_approved(self, query):
        return query.where("approved", 1)


class ScopeUser(Model):
    __table__ = "scope_users"
    __timestamps__ = False

    name: str
    roles: "ScopeRole" = BelongsToMany(
        "ScopeRole",
        local_foreign_key="user_id",
        other_foreign_key="role_id",
        table="role_scope_user",
    )


class ScopeRole(Model):
    __table__ = "scope_roles"
    __timestamps__ = False

    name: str


class TestGlobalScopes(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("scoped_posts") as table:
            table.integer("id").primary()
            table.string("title")
            table.integer("published")
        async with await self.schema.create_table_if_not_exists("discovered_comments") as table:
            table.integer("id").primary()
            table.string("body")
            table.integer("approved")
        async with await self.schema.create_table_if_not_exists("scope_users") as table:
            table.integer("id").primary()
            table.string("name")
        async with await self.schema.create_table_if_not_exists("scope_roles") as table:
            table.integer("id").primary()
            table.string("name")
        async with await self.schema.create_table_if_not_exists("role_scope_user") as table:
            table.integer("user_id")
            table.integer("role_id")

        await ScopedPost.create({"title": "first", "published": 1})
        await ScopedPost.create({"title": "second", "published": 1})
        await ScopedPost.create({"title": "draft", "published": 0})

    async def asyncTearDown(self):
        for name in (
            "role_scope_user",
            "scope_roles",
            "scope_users",
            "discovered_comments",
            "scoped_posts",
        ):
            await self.schema.drop_table_if_exists(name)
        await super().asyncTearDown()

    async def test_declared_global_scope_filters_get(self):
        posts = await ScopedPost.get()
        assert len(posts) == 2
        assert all(int(post.published) == 1 for post in posts)

    async def test_global_scope_is_compiled_into_sql(self):
        sql = ScopedPost.query().to_sql()
        assert "published" in sql

    async def test_without_global_scopes_bypasses_filter(self):
        # Mutation check: the declared scope would otherwise drop this to 2.
        posts = await ScopedPost.query().without_global_scopes().get()
        assert len(posts) == 3

    async def test_model_without_global_scopes_helper(self):
        posts = await ScopedPost.without_global_scopes().get()
        assert len(posts) == 3

    async def test_scope_star_method_is_discovered(self):
        await DiscoveredComment.create({"body": "ok", "approved": 1})
        await DiscoveredComment.create({"body": "spam", "approved": 0})

        approved = await DiscoveredComment.get()
        assert len(approved) == 1
        assert int(approved.first().approved) == 1

        every = await DiscoveredComment.without_global_scopes().get()
        assert len(every) == 2

    async def test_add_global_scope_registration(self):
        ScopeRole.add_global_scope("only_admin", lambda query: query.where("name", "admin"))
        try:
            await ScopeRole.create({"name": "admin"})
            await ScopeRole.create({"name": "guest"})

            scoped = await ScopeRole.get()
            assert len(scoped) == 1
            assert scoped.first().name == "admin"

            # Mutation check: bypassing the freshly registered scope returns both rows.
            assert len(await ScopeRole.without_global_scopes().get()) == 2
        finally:
            ScopeRole.__global_scopes__ = {}

    async def test_belongs_to_many_attach_pivot_path(self):
        user = await ScopeUser.create({"name": "Sam"})
        role = await ScopeRole.create({"name": "editor"})

        inserted = await ScopeUser.roles.attach(user, role)
        assert inserted is not None

        rows = await ScopeUser.query().table("role_scope_user").get()
        assert len(rows) == 1
        assert int(rows.first().user_id) == user.id
        assert int(rows.first().role_id) == role.id

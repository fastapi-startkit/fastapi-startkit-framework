from fastapi_startkit.masoniteorm import Model

from ..fixtures.db import DB
from ..test_case import TestCase


class Category(Model):
    __table__ = "categories"
    __timestamps__ = None
    id: int
    name: str


class Post(Model):
    __table__ = "posts"
    __timestamps__ = None
    id: int
    title: str
    category_id: int


class Account(Model):
    __table__ = "accounts"
    __timestamps__ = None
    id: int
    name: str


class Login(Model):
    __table__ = "logins"
    __timestamps__ = None
    id: int
    user_id: int
    created_at: str


def category_name_subquery():
    return Category.query().select("name").where_column("categories.id", "posts.category_id").limit(1)


class TestSqliteSelectSub(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        conn = DB.connection("default")
        await conn.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        await conn.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT, category_id INTEGER)")
        await conn.execute("INSERT INTO categories (id, name) VALUES (1, 'Zebra'), (2, 'Apple'), (3, 'Mango')")
        await conn.execute(
            "INSERT INTO posts (id, title, category_id) VALUES (1, 'z', 1), (2, 'a', 2), (3, 'm', 3), (4, 'a2', 2)"
        )
        await conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT)")
        await conn.execute("CREATE TABLE logins (id INTEGER PRIMARY KEY, user_id INTEGER, created_at TEXT)")
        await conn.execute("INSERT INTO accounts (id, name) VALUES (1, 'Alice'), (2, 'Bob')")
        await conn.execute(
            "INSERT INTO logins (id, user_id, created_at) VALUES "
            "(1, 1, '2024-01-01'), (2, 1, '2024-03-01'), (3, 2, '2024-02-01')"
        )

    async def test_select_sub_with_builder(self):
        posts = await (
            Post.query()
            .select("id", "title")
            .select_sub(category_name_subquery(), "category_name")
            .order_by("id")
            .get()
        )
        pairs = [(p.id, p.serialize()["category_name"]) for p in posts]
        self.assertEqual(pairs, [(1, "Zebra"), (2, "Apple"), (3, "Mango"), (4, "Apple")])

    async def test_select_sub_with_callable(self):
        posts = await (
            Post.query()
            .select("id")
            .select_sub(
                lambda q: (
                    q.table("categories").select("name").where_column("categories.id", "posts.category_id").limit(1)
                ),
                "category_name",
            )
            .order_by("id")
            .get()
        )
        self.assertEqual([p.serialize()["category_name"] for p in posts], ["Zebra", "Apple", "Mango", "Apple"])

    async def test_add_select_variadic_columns(self):
        posts = await Post.query().select("id").add_select("title", "category_id").order_by("id").get()
        self.assertEqual(
            [(p.id, p.title, p.category_id) for p in posts], [(1, "z", 1), (2, "a", 2), (3, "m", 3), (4, "a2", 2)]
        )

    async def test_add_select_associative_subquery_acceptance_case(self):
        # Mirrors Laravel: addSelect(['last_login_at' => Logins::select('created_at')
        #   ->whereColumn('user_id','users.id')->latest()->take(1)]) — take(1) => limit(1).
        accounts = (
            await Account.query()
            .add_select(
                {
                    "last_login_at": Login.query()
                    .select("created_at")
                    .where_column("user_id", "accounts.id")
                    .latest()
                    .limit(1)
                }
            )
            .order_by("id")
            .get()
        )
        result = {a.name: a.serialize()["last_login_at"] for a in accounts}
        self.assertEqual(result, {"Alice": "2024-03-01", "Bob": "2024-02-01"})

    async def test_add_select_associative_seeds_table_star(self):
        # No prior select(): base columns must still be present (seeded via {table}.*).
        accounts = (
            await Account.query()
            .add_select(
                {
                    "last_login_at": Login.query()
                    .select("created_at")
                    .where_column("user_id", "accounts.id")
                    .latest()
                    .limit(1)
                }
            )
            .order_by("id")
            .get()
        )
        self.assertEqual([a.name for a in accounts], ["Alice", "Bob"])

    async def test_table_setter_overrides_target_table(self):
        rows = await Post.query().table("categories").select("name").order_by("id").get()
        self.assertEqual([r.serialize()["name"] for r in rows], ["Zebra", "Apple", "Mango"])

    async def test_select_sub_with_join_shaped_callable_compiles_and_runs(self):
        # The shape the migrated *Through/BelongsToMany with-count callers now use:
        # select_sub(callable that sets table + joins + where_column, alias). This
        # asserts the real correlated subquery-as-column compiles (JOIN, correlated
        # column, alias all present) and executes. The relationship methods' own
        # end-to-end with-count is fixed separately — it needs a synchronous COUNT
        # subquery instead of the async count() coroutine (see #886).
        query = (
            Post.query()
            .select("posts.id")
            .select_sub(
                lambda q: (
                    q.table("categories")
                    .select("name")
                    .join("posts", "posts.category_id", "=", "categories.id")
                    .where_column("categories.id", "posts.category_id")
                    .limit(1)
                ),
                "joined_name",
            )
        )
        sql = query.to_sql()
        self.assertIn("JOIN", sql)
        self.assertIn("categories.id = posts.category_id", sql)
        self.assertIn("AS joined_name", sql)

        rows = await query.order_by("posts.id").get()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all("joined_name" in r.serialize() for r in rows))

from ...fixtures.model import User
from ..test_case import TestCase

# ---------------------------------------------------------------------------
# Dataset under test
#
# The shared seeder already creates two users; this suite adds a third (Alice)
# in setUp, giving a controlled three-row table:
#
#   id  name   email              is_admin  email_verified_at
#   1   Joe    admin@admin.com    True      2024-01-15 08:00:00
#   2   Jane   guest@guest.com    False     NULL
#   3   Alice  alice@example.com  True      2024-01-01 00:00:00
#
# So: admins/verified = {Joe, Alice}; non-admin/unverified = {Jane}.
# ---------------------------------------------------------------------------


class QueryTestCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()  # migrates + seeds Joe & Jane
        await User.query().create(
            {
                "name": "Alice",
                "email": "alice@example.com",
                "is_admin": True,
                "email_verified_at": "2024-01-01 00:00:00",
            }
        )


# ---------------------------------------------------------------------------
# WHERE
# ---------------------------------------------------------------------------


class TestWhere(QueryTestCase):
    async def test_where_equals(self):
        results = await User.where("name", "Alice").get()
        self.assertEqual(len(results), 1)
        self.assertEqual(results.first().name, "Alice")

    async def test_where_with_explicit_operator(self):
        results = await User.where("name", "!=", "Alice").get()
        self.assertEqual(len(results), 2)  # Joe, Jane

    async def test_where_like(self):
        results = await User.where("name", "like", "%li%").get()
        # Only "Alice" contains "li".
        self.assertEqual(len(results), 1)
        self.assertEqual(results.first().name, "Alice")

    async def test_where_chained(self):
        results = await User.where("is_admin", False).where("name", "Jane").get()
        self.assertEqual(len(results), 1)
        self.assertEqual(results.first().name, "Jane")

    async def test_where_dict(self):
        results = await User.where({"name": "Alice", "is_admin": True}).get()
        self.assertEqual(len(results), 1)

    async def test_where_returns_empty_collection_when_no_match(self):
        results = await User.where("name", "Nobody").get()
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# OR WHERE
# ---------------------------------------------------------------------------


class TestOrWhere(QueryTestCase):
    async def test_or_where_matches_either_condition(self):
        results = await User.where("name", "Alice").or_where("name", "Jane").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Alice", "Jane"})

    async def test_or_where_no_match_returns_empty(self):
        results = await User.where("name", "Nobody").or_where("name", "Ghost").get()
        self.assertEqual(len(results), 0)

    async def test_or_where_like(self):
        # Match names starting with 'A' OR ending with 'e'.
        results = await User.where("name", "like", "A%").or_where("name", "like", "%e").get()
        names = {u.name for u in results}
        # "Alice" starts with A; "Joe", "Jane", "Alice" all end with 'e'.
        self.assertEqual(names, {"Joe", "Jane", "Alice"})


# ---------------------------------------------------------------------------
# WHERE IN
# ---------------------------------------------------------------------------


class TestWhereIn(QueryTestCase):
    async def test_where_in_matches_list(self):
        results = await User.query().where_in("name", ["Alice", "Jane"]).get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Alice", "Jane"})

    async def test_where_in_empty_list_returns_empty(self):
        results = await User.query().where_in("name", []).get()
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------


class TestSelect(QueryTestCase):
    async def test_select_single_column(self):
        results = await User.query().select("name").get()
        first = results.first()
        self.assertIsNotNone(first.name)
        # email was not selected — should be None or missing.
        self.assertIsNone(getattr(first, "email", None))

    async def test_select_multiple_columns(self):
        results = await User.query().select("name", "email").get()
        first = results.first()
        self.assertIsNotNone(first.name)
        self.assertIsNotNone(first.email)


# ---------------------------------------------------------------------------
# LIMIT
# ---------------------------------------------------------------------------


class TestLimit(QueryTestCase):
    async def test_limit_restricts_result_count(self):
        results = await User.query().limit(2).get()
        self.assertEqual(len(results), 2)

    async def test_limit_one_equals_first(self):
        by_limit = await User.query().limit(1).get()
        by_first = await User.first()
        assert by_first is not None
        self.assertEqual(by_limit.first().id, by_first.id)


# ---------------------------------------------------------------------------
# FIRST
# ---------------------------------------------------------------------------


class TestFirst(QueryTestCase):
    async def test_first_returns_single_model(self):
        user = await User.first()
        self.assertIsInstance(user, User)

    async def test_first_returns_none_when_empty(self):
        await User.query().delete()
        user = await User.first()
        self.assertIsNone(user)

    async def test_first_with_where(self):
        user = await User.where("name", "Jane").first()
        assert user is not None
        self.assertEqual(user.name, "Jane")


# ---------------------------------------------------------------------------
# FIND
# ---------------------------------------------------------------------------


class TestFind(QueryTestCase):
    async def test_find_by_primary_key(self):
        first_user = await User.first()
        assert first_user is not None
        found = await User.find(first_user.id)
        assert found is not None
        self.assertEqual(found.id, first_user.id)

    async def test_find_returns_none_for_missing_id(self):
        found = await User.find(99999)
        self.assertIsNone(found)


# ---------------------------------------------------------------------------
# FIRST OR CREATE
# ---------------------------------------------------------------------------


class TestFirstOrCreate(QueryTestCase):
    async def test_first_or_create_returns_existing(self):
        existing = await User.where("email", "alice@example.com").first()
        assert existing is not None
        result = await User.query().first_or_create(
            {"email": "alice@example.com"},
            {"name": "Alice New"},
        )
        # Should return the existing record, not create a new one.
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.name, "Alice")

    async def test_first_or_create_inserts_when_missing(self):
        user = await User.query().first_or_create(
            {"email": "new@example.com"},
            {"name": "New User"},
        )
        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.name, "New User")

        # Calling again should return the same record.
        user2 = await User.query().first_or_create({"email": "new@example.com"})
        self.assertEqual(user2.id, user.id)


# ---------------------------------------------------------------------------
# BULK INSERT  (baseline is the three seeded rows)
# ---------------------------------------------------------------------------


class TestBulkInsert(QueryTestCase):
    async def test_insert_list_of_dicts(self):
        await User.query().insert(
            [
                {"name": "Dave", "email": "dave@example.com"},
                {"name": "Eve", "email": "eve@example.com"},
            ]
        )
        results = await User.query().get()
        self.assertEqual(len(results), 5)  # Joe, Jane, Alice + Dave, Eve

    async def test_insert_single_dict(self):
        await User.query().insert({"name": "Frank", "email": "frank@example.com"})
        results = await User.query().get()
        self.assertEqual(len(results), 4)

    async def test_insert_empty_list_is_noop(self):
        result = await User.query().insert([])
        self.assertIsNone(result)
        results = await User.query().get()
        self.assertEqual(len(results), 3)


# ---------------------------------------------------------------------------
# QUERY-LEVEL UPDATE
# ---------------------------------------------------------------------------


class TestQueryUpdate(QueryTestCase):
    async def test_update_all_records(self):
        await User.query().update({"is_admin": True})
        results = await User.where("is_admin", True).get()
        self.assertEqual(len(results), 3)

    async def test_update_with_where_filter(self):
        await User.where("name", "Jane").update({"name": "Janet"})
        janet = await User.where("name", "Janet").first()
        assert janet is not None
        self.assertEqual(janet.name, "Janet")

        old_jane = await User.where("name", "Jane").first()
        self.assertIsNone(old_jane)


# ---------------------------------------------------------------------------
# COMBINED SCENARIOS
# ---------------------------------------------------------------------------


class TestCombinedQueries(QueryTestCase):
    async def test_where_and_limit(self):
        results = await User.where("is_admin", False).limit(1).get()
        self.assertEqual(len(results), 1)  # only Jane is non-admin

    async def test_where_and_select(self):
        results = await User.where("is_admin", True).select("name").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Joe", "Alice"})

    async def test_or_where_and_limit(self):
        results = await User.where("name", "Alice").or_where("name", "Jane").limit(1).get()
        self.assertEqual(len(results), 1)


# ---------------------------------------------------------------------------
# OR WHERE NULL / OR WHERE NOT NULL
#
# Verified (NOT NULL): Joe, Alice.  Unverified (NULL): Jane.
# ---------------------------------------------------------------------------


class TestOrWhereNull(QueryTestCase):
    async def test_or_where_null_returns_combined_rows(self):
        # where(name=Alice) OR email_verified_at IS NULL → Alice + Jane.
        results = await User.where("name", "Alice").or_where_null("email_verified_at").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Alice", "Jane"})

    async def test_or_where_null_with_no_base_where(self):
        # No leading where — just the NULL rows (Jane).
        results = await User.query().or_where_null("email_verified_at").get()
        names = {u.name for u in results}
        self.assertIn("Jane", names)

    async def test_or_where_null_does_not_lose_base_match(self):
        base = await User.where("name", "Alice").get()
        self.assertEqual(len(base), 1)

        combined = await User.where("name", "Alice").or_where_null("email_verified_at").get()
        self.assertEqual(len(combined), 2)  # Alice + Jane


class TestOrWhereNotNull(QueryTestCase):
    async def test_or_where_not_null_returns_combined_rows(self):
        # where(name=Jane) OR email_verified_at IS NOT NULL → Jane + Joe + Alice.
        results = await User.where("name", "Jane").or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Joe", "Jane", "Alice"})

    async def test_or_where_not_null_with_no_base_where(self):
        results = await User.query().or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Joe", "Alice"})

    async def test_or_where_not_null_excludes_null_only_rows(self):
        # where(name=Nobody) OR email_verified_at IS NOT NULL → Joe + Alice.
        results = await User.where("name", "Nobody").or_where_not_null("email_verified_at").get()
        names = {u.name for u in results}
        self.assertEqual(names, {"Joe", "Alice"})


# ---------------------------------------------------------------------------
# WHERE RAW
# ---------------------------------------------------------------------------


class TestWhereRaw(QueryTestCase):
    async def test_where_raw_with_binding(self):
        results = await User.where_raw("name = ?", bindings=("Alice",)).get()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alice")

    async def test_where_raw_without_bindings(self):
        # Filter admins without a binding → Joe, Alice.
        results = await User.where_raw("is_admin = 1").get()
        names = {r.name for r in results}
        self.assertEqual(names, {"Joe", "Alice"})

    async def test_where_raw_chained_with_where(self):
        # Normal where then raw — AND logic applies.
        results = await User.where("is_admin", False).where_raw("name = ?", bindings=("Jane",)).get()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Jane")

    async def test_where_raw_no_match_returns_empty(self):
        results = await User.where_raw("name = ?", bindings=("Nobody",)).get()
        self.assertEqual(len(results), 0)


# ---------------------------------------------------------------------------
# OR WHERE RAW
# ---------------------------------------------------------------------------


class TestOrWhereRaw(QueryTestCase):
    async def test_or_where_raw_with_binding(self):
        results = await User.where("name", "Alice").or_where_raw("name = ?", bindings=("Jane",)).get()
        names = {r.name for r in results}
        self.assertEqual(names, {"Alice", "Jane"})

    async def test_or_where_raw_no_bindings(self):
        # No bindings arg provided — must not raise on tuple vs list.
        results = await User.where("name", "Alice").or_where_raw("name IS NOT NULL").get()
        self.assertGreater(len(results), 0)

    async def test_or_where_raw_three_way_union(self):
        results = (
            await User.where("name", "Joe")
            .or_where_raw("name = ?", bindings=("Jane",))
            .or_where_raw("name = ?", bindings=("Alice",))
            .get()
        )
        names = {r.name for r in results}
        self.assertEqual(names, {"Joe", "Jane", "Alice"})

    async def test_or_where_raw_no_match_returns_only_base(self):
        results = await User.where("name", "Alice").or_where_raw("name = ?", bindings=("Nobody",)).get()
        names = {r.name for r in results}
        self.assertEqual(names, {"Alice"})

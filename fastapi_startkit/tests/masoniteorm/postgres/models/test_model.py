import datetime

from ..test_case import TestCase
from ...fixtures.model import User
from ..fixtures.db import DB


class TestPostGresModel(TestCase):
    async def test_can_create_and_find_user(self):
        user = await User.create({"name": "Alice", "email": "alice@example.com", "is_admin": False})
        self.assertIsNotNone(user.id)

        found = await User.find(user.id)
        self.assertEqual(found.name, "Alice")
        self.assertEqual(found.email, "alice@example.com")

    async def test_find_returns_none_for_missing_id(self):
        found = await User.find(99999)
        self.assertIsNone(found)

    async def test_first_returns_first_record(self):
        await User.create({"name": "Bob", "email": "bob@example.com", "is_admin": False})
        await User.create({"name": "Carol", "email": "carol@example.com", "is_admin": True})

        user = await User.first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Bob")

    async def test_first_returns_none_when_table_is_empty(self):
        user = await User.first()
        self.assertIsNone(user)

    async def test_update_changes_attributes(self):
        user = await User.create({"name": "Dave", "email": "dave@example.com", "is_admin": False})

        await user.update({"name": "David"})

        refreshed = await User.find(user.id)
        self.assertEqual(refreshed.name, "David")
        self.assertEqual(refreshed.email, "dave@example.com")

    async def test_update_only_dirty_fields(self):
        user = await User.create({"name": "Eve", "email": "eve@example.com", "is_admin": False})

        await user.update({"name": "Eve", "is_admin": True})

        refreshed = await User.find(user.id)
        self.assertTrue(refreshed.is_admin)
        self.assertEqual(refreshed.name, "Eve")

    async def test_delete_removes_record(self):
        user = await User.create({"name": "Frank", "email": "frank@example.com", "is_admin": False})
        user_id = user.id

        await User.where("id", user_id).delete()

        found = await User.find(user_id)
        self.assertIsNone(found)

    async def test_delete_by_column_removes_matching_records(self):
        await User.create({"name": "Grace", "email": "grace@example.com", "is_admin": False})
        await User.create({"name": "Heidi", "email": "heidi@example.com", "is_admin": True})

        await User.query().delete("is_admin", True)

        admin = await User.where("is_admin", True).first()
        self.assertIsNone(admin)

        non_admin = await User.where("is_admin", False).first()
        self.assertIsNotNone(non_admin)

    async def test_where_filters_results(self):
        await User.create({"name": "Ivan", "email": "ivan@example.com", "is_admin": False})
        await User.create({"name": "Judy", "email": "judy@example.com", "is_admin": True})

        admins = await User.where("is_admin", True).get()
        self.assertEqual(len(admins), 1)
        self.assertEqual(admins[0].name, "Judy")

    async def test_first_or_create_creates_when_not_found(self):
        user = await User.first_or_create(
            {"email": "newuser@example.com"},
            {"name": "New User", "is_admin": False},
        )
        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "newuser@example.com")
        self.assertEqual(user.name, "New User")

    async def test_first_or_create_returns_existing_when_found(self):
        existing = await User.create({"name": "Existing", "email": "existing@example.com", "is_admin": False})

        user = await User.first_or_create(
            {"email": "existing@example.com"},
            {"name": "Should Not Be Created", "is_admin": True},
        )
        self.assertEqual(user.id, existing.id)
        self.assertEqual(user.name, "Existing")

        # Confirm no duplicate was inserted
        all_users = await User.where("email", "existing@example.com").get()
        self.assertEqual(len(all_users), 1)

    async def test_all_returns_all_records(self):
        await User.create({"name": "Karl", "email": "karl@example.com", "is_admin": False})
        await User.create({"name": "Laura", "email": "laura@example.com", "is_admin": False})

        users = await User.all()
        self.assertEqual(len(users), 2)

    async def test_update_or_create_creates_when_not_found(self):
        user = await User.update_or_create(
            {"email": "new@example.com"},
            {"name": "New User", "is_admin": False},
        )
        self.assertIsNotNone(user.id)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.name, "New User")

    async def test_update_or_create_updates_when_found(self):
        await User.create({"name": "Original", "email": "update@example.com", "is_admin": False})

        user = await User.update_or_create(
            {"email": "update@example.com"},
            {"name": "Updated", "is_admin": True},
        )
        self.assertEqual(user.name, "Updated")
        self.assertTrue(user.is_admin)

        # Confirm no duplicate was inserted
        count = await User.where("email", "update@example.com").count()
        self.assertEqual(count, 1)

    async def test_count_returns_correct_number(self):
        await User.create({"name": "Mallory", "email": "mallory@example.com", "is_admin": False})
        await User.create({"name": "Niaj", "email": "niaj@example.com", "is_admin": False})

        count = await User.count()
        self.assertEqual(count, 2)

    async def test_insert_single_row(self):
        await User.insert({"name": "Olivia", "email": "olivia@example.com", "is_admin": False})

        user = await User.where("email", "olivia@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Olivia")

    async def test_insert_bulk_rows(self):
        await User.insert(
            [
                {"name": "Peggy", "email": "peggy@example.com", "is_admin": False},
                {"name": "Quentin", "email": "quentin@example.com", "is_admin": True},
            ]
        )

        count = await User.count()
        self.assertEqual(count, 2)

        admin = await User.where("is_admin", True).first()
        self.assertEqual(admin.name, "Quentin")

    async def test_supplied_created_at_is_stored_exactly(self):
        supplied = datetime.datetime(2020, 1, 2, 3, 4, 5, 678000, tzinfo=datetime.UTC)

        user = await User.create({"name": "Stamp", "email": "stamp@example.com", "created_at": supplied})

        row = await DB.connection("postgres").select_one('SELECT "created_at" FROM "users" WHERE "id" = ?', [user.id])
        self.assertIsNotNone(row)
        self.assertEqual(row["created_at"], supplied)

    async def test_update_and_touch_move_updated_at_forward(self):
        user = await User.create({"name": "Toucher", "email": "toucher@example.com"})
        created_at, inserted_updated_at = user.created_at, user.updated_at

        await user.update({"name": "Touched"})
        updated = await User.find(user.id)
        self.assertGreater(updated.updated_at, inserted_updated_at)
        self.assertEqual(updated.created_at, created_at)

        self.assertTrue(await user.touch())
        touched = await User.find(user.id)
        self.assertGreater(touched.updated_at, updated.updated_at)

    async def test_timestamp_and_timestamptz_columns_store_the_same_instant_for_aware_and_naive_input(self):
        instant = datetime.datetime(2020, 1, 2, 3, 4, 5, 678000, tzinfo=datetime.UTC)
        inputs = {
            "aware": instant.astimezone(datetime.timezone(datetime.timedelta(hours=-4))),
            "naive": instant.replace(tzinfo=None),
        }

        for label, value in inputs.items():
            with self.subTest(label):
                user = await User.create(
                    {"name": label, "email": f"{label}@example.com", "email_verified_at": value, "created_at": value}
                )

                row = await DB.connection("postgres").select_one(
                    'SELECT "email_verified_at", "created_at" FROM "users" WHERE "id" = ?', [user.id]
                )
                self.assertIsNotNone(row)
                self.assertEqual(row["email_verified_at"], instant.replace(tzinfo=None))
                self.assertEqual(row["created_at"], instant)

                found = await User.find(user.id)
                self.assertEqual(found.email_verified_at, instant)
                self.assertEqual(found.created_at, instant)

    async def test_raw_bindings_keep_the_instant_on_timestamp_and_timestamptz_columns(self):
        instant = datetime.datetime(2021, 6, 7, 8, 9, 10, 123456, tzinfo=datetime.UTC)
        aware = instant.astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        connection = DB.connection("postgres")

        row = await connection.select_one(
            "SELECT CAST(? AS timestamp) AS from_aware, CAST(? AS timestamp) AS from_naive, "
            "CAST(? AS timestamptz) AS tz_from_aware",
            [aware, instant.replace(tzinfo=None), aware],
        )

        self.assertIsNotNone(row)
        self.assertEqual(row["from_aware"], instant.replace(tzinfo=None))
        self.assertEqual(row["from_naive"], instant.replace(tzinfo=None))
        self.assertEqual(row["tz_from_aware"], instant)

    async def test_timestamp_infinity_maps_to_datetime_bounds(self):
        row = await DB.connection("postgres").select_one(
            "SELECT CAST(? AS timestamp) = 'infinity' AS is_infinity, CAST(? AS timestamp) = '-infinity' AS is_negative, "
            "CAST('infinity' AS timestamp) AS infinity, CAST('-infinity' AS timestamp) AS negative",
            [datetime.datetime.max, datetime.datetime.min],
        )

        self.assertIsNotNone(row)
        self.assertTrue(row["is_infinity"])
        self.assertTrue(row["is_negative"])
        self.assertEqual(row["infinity"], datetime.datetime.max)
        self.assertEqual(row["negative"], datetime.datetime.min)

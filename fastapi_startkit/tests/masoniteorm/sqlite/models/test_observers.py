import datetime

from fastapi_startkit.masoniteorm.models.caster import DateCast
from fastapi_startkit.masoniteorm.models.model import Model
from ..test_case import TestCase


class TestM:
    pass


class UserObserver:
    def created(self, user):
        TestM.observed_created = True

    def creating(self, user):
        TestM.observed_creating = True

    def saving(self, user):
        TestM.observed_saving = True

    def saved(self, user):
        TestM.observed_saved = True

    def updated(self, user):
        TestM.observed_updated = True

    def updating(self, user):
        TestM.observed_updating = True


class ObservedUser(Model):
    __table__ = "users"
    __timestamps__ = False
    __observers__ = {}
    name: str
    email: str
    is_admin: bool


ObservedUser.observe(UserObserver())


class TestObservers(TestCase):
    async def test_created_is_observed(self):
        await ObservedUser.create({"name": "joe", "email": "obs@test.com", "is_admin": False})
        assert getattr(TestM, "observed_created", False)

    async def test_saving_is_observed(self):
        await ObservedUser.create({"name": "saveable", "email": "save@test.com", "is_admin": False})
        assert getattr(TestM, "observed_saving", False)
        assert getattr(TestM, "observed_saved", False)

    async def test_updating_is_observed(self):
        user = await ObservedUser.create({"name": "updatable", "email": "update@test.com", "is_admin": False})
        await user.update({"name": "updated_name"})
        assert getattr(TestM, "observed_updated", False)


class RecordingObserver:
    def __init__(self):
        self.events: list[str] = []

    def saving(self, user):
        self.events.append("saving")

    def creating(self, user):
        self.events.append("creating")
        user.address = "set while creating"

    def created(self, user):
        self.events.append("created")

    def updating(self, user):
        self.events.append("updating")
        user.address = "set while updating"

    def updated(self, user):
        self.events.append("updated")

    def saved(self, user):
        self.events.append("saved")

    def deleting(self, user):
        self.events.append("deleting")

    def deleted(self, user):
        self.events.append("deleted")


class AsyncRecordingObserver:
    def __init__(self):
        self.events: list[str] = []

    async def creating(self, user):
        self.events.append("creating")
        user.address = "async creating"

    async def updating(self, user):
        self.events.append("updating")
        user.address = "async updating"

    async def deleting(self, user):
        row = await AsyncObservedUser.find(user.id)
        self.events.append(f"deleting:{row is not None}")

    async def deleted(self, user):
        self.events.append("deleted")


class RecordedUser(Model):
    __table__ = "users"
    __timestamps__ = False
    __observers__ = {}
    name: str
    email: str
    address: str


class AsyncObservedUser(Model):
    __table__ = "users"
    __timestamps__ = False
    __observers__ = {}
    name: str
    email: str
    address: str


recorder = RecordingObserver()
RecordedUser.observe(recorder)

async_recorder = AsyncRecordingObserver()
AsyncObservedUser.observe(async_recorder)


class TestModelLifecycleEvents(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        recorder.events.clear()
        async_recorder.events.clear()

    async def test_insert_fires_creating_between_saving_and_created(self):
        await RecordedUser.create({"name": "order", "email": "order@test.com"})

        assert recorder.events == ["saving", "creating", "created", "saved"]

    async def test_creating_mutation_is_persisted(self):
        user = await RecordedUser.create({"name": "creating", "email": "creating@test.com"})

        fresh = await RecordedUser.find(user.id)
        assert fresh is not None
        assert fresh.address == "set while creating"

    async def test_update_fires_updating_between_saving_and_updated(self):
        user = await RecordedUser.create({"name": "before", "email": "upd@test.com"})
        recorder.events.clear()

        await user.update({"name": "after"})

        assert recorder.events == ["saving", "updating", "updated", "saved"]

    async def test_updating_mutation_is_persisted(self):
        user = await RecordedUser.create({"name": "before", "email": "upd2@test.com"})

        await user.update({"name": "after"})

        fresh = await RecordedUser.find(user.id)
        assert fresh is not None
        assert fresh.name == "after"
        assert fresh.address == "set while updating"

    async def test_clean_save_skips_updating(self):
        user = await RecordedUser.create({"name": "clean", "email": "clean@test.com"})
        recorder.events.clear()

        await user.save()

        assert recorder.events == ["saving", "saved"]

    async def test_delete_fires_deleting_and_deleted(self):
        user = await RecordedUser.create({"name": "gone", "email": "gone@test.com"})
        recorder.events.clear()

        assert await user.delete() is True

        assert recorder.events == ["deleting", "deleted"]
        assert await RecordedUser.find(user.id) is None

    async def test_delete_on_unsaved_model_is_a_noop(self):
        user = RecordedUser().new_model_instance({"name": "never", "email": "never@test.com"})

        assert await user.delete() is False
        assert recorder.events == []

    async def test_async_observer_methods_are_awaited(self):
        user = await AsyncObservedUser.create({"name": "async", "email": "async@test.com"})
        fresh = await AsyncObservedUser.find(user.id)
        assert fresh is not None
        assert fresh.address == "async creating"

        await user.update({"name": "async2"})
        fresh = await AsyncObservedUser.find(user.id)
        assert fresh is not None
        assert fresh.address == "async updating"

        await user.delete()

        assert async_recorder.events == ["creating", "updating", "deleting:True", "deleted"]
        assert await AsyncObservedUser.find(user.id) is None

    async def test_without_events_skips_observers(self):
        RecordedUser.without_events()
        try:
            user = await RecordedUser.create({"name": "silent", "email": "silent@test.com"})
            await user.delete()
        finally:
            RecordedUser.with_events()

        assert recorder.events == []


class Note(Model):
    __table__ = "notes"
    body: str


class UntimedNote(Model):
    __table__ = "notes"
    __timestamps__ = False
    body: str


class TestAutomaticTimestamps(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with await self.schema.create_table_if_not_exists("notes") as table:
            table.id()
            table.string("body")
            table.timestamp("created_at", nullable=True)
            table.timestamp("updated_at", nullable=True)

    async def test_create_sets_both_timestamps_without_a_column_default(self):
        note = await Note.create({"body": "first"})

        fresh = await Note.find(note.id)
        assert fresh is not None
        assert fresh.created_at is not None
        assert fresh.created_at == note.created_at
        assert fresh.updated_at == note.updated_at

    async def test_create_keeps_a_supplied_created_at(self):
        supplied = datetime.datetime(
            2020, 1, 2, 8, 34, 5, 678000, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        )

        note = await Note.create({"body": "supplied", "created_at": supplied})

        fresh = await Note.find(note.id)
        assert fresh is not None
        assert fresh.created_at == supplied
        assert fresh.created_at.microsecond == 678000
        assert fresh.created_at.timezone_name == "UTC"

    async def test_update_moves_updated_at_and_keeps_created_at(self):
        note = await Note.create({"body": "before"})
        created_at, updated_at = note.created_at, note.updated_at

        await note.update({"body": "after"})

        fresh = await Note.find(note.id)
        assert fresh is not None
        assert fresh.created_at == created_at
        assert fresh.updated_at > updated_at

    async def test_disabled_timestamps_are_not_written(self):
        note = await UntimedNote.create({"body": "plain"})
        await note.update({"body": "still plain"})

        fresh = await UntimedNote.find(note.id)
        assert fresh is not None
        assert fresh.created_at is None
        assert fresh.updated_at is None


class TestSQLiteDatetimeBinding(TestCase):
    async def test_datetime_round_trips_in_utc(self):
        written = datetime.datetime(2024, 5, 6, 7, 8, 9, 123456, tzinfo=datetime.timezone(datetime.timedelta(hours=-4)))
        user = await ObservedUser.create({"name": "bind", "email": "bind@test.com", "is_admin": False})

        await ObservedUser.where("id", user.id).update({"email_verified_at": DateCast().set(written)})

        row = await self.db.connection("default").select_one(
            'SELECT "email_verified_at" FROM "users" WHERE "id" = ?', [user.id]
        )
        assert row is not None
        assert row["email_verified_at"] == "2024-05-06 11:08:09.123456"
        assert DateCast().get(row["email_verified_at"]) == written

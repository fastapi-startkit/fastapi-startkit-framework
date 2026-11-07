import importlib.util
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase, mock

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastapi_startkit.application import Application
from fastapi_startkit.configuration import config
from fastapi_startkit.exceptions import NotificationException
from fastapi_startkit.facades import Mail
from fastapi_startkit.facades import Notification as NotificationFacade
from fastapi_startkit.mail import ArrayMailerConfig, Mailable, MailProvider
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm.schema import Schema
from fastapi_startkit.notifications import (
    ChannelManager,
    MailMessage,
    Notifiable,
    Notification,
    NotificationProvider,
)

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "src/fastapi_startkit/notifications/migrations/2026_11_06_000000_create_notifications_table.py"
)


class NotifiedUser(Model, Notifiable):
    __table__ = "users"


class InvoicePaid(Notification):
    def __init__(self, amount: int, channels=("mail", "database")):
        self.amount = amount
        self.channels = list(channels)

    def via(self, notifiable):
        return self.channels

    def to_mail(self, notifiable):
        return (
            MailMessage()
            .subject("Invoice paid")
            .greeting(f"Hello {getattr(notifiable, 'name', 'there')}")
            .line(f"We received {self.amount}.")
            .action("View invoice", "https://example.com/invoices/1?a=1&b=2")
        )

    def to_array(self, notifiable):
        return {"amount": self.amount}


class NoMail(Notification):
    def via(self, notifiable):
        return ["mail"]


class DatabaseOnly(Notification):
    def via(self, notifiable):
        return ["database"]

    def to_database(self, notifiable):
        return {"source": "to_database"}


@dataclass
class MailConfig:
    default: str = "array"
    from_address: str = "app@example.com"
    from_name: str = "App"
    mailers: dict = field(default_factory=lambda: {"array": ArrayMailerConfig(), "second": ArrayMailerConfig()})


class InMemoryDatabase:
    def __init__(self):
        self.engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.sqlite = SQliteConnection(self.engine, SQLiteConfig(database=":memory:"))
        self.requested = []

    def connection(self, name=None):
        self.requested.append(name)
        return self.sqlite


def load_migration():
    spec = importlib.util.spec_from_file_location("create_notifications_table", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMailMessage(TestCase):
    def test_renders_text_and_escaped_html(self):
        message = (
            MailMessage()
            .to("a@example.com")
            .subject("Hi")
            .greeting("Hello <Ann>")
            .line("Line one")
            .action("Open", "https://example.com/?a=1&b=2")
            .salutation("Bye")
            .to_message()
        )

        text = message.get_body(("plain",)).get_content()
        html = message.get_body(("html",)).get_content()
        self.assertIn("Hello <Ann>\n\nLine one\n\nOpen: https://example.com/?a=1&b=2\n\nBye", text)
        self.assertIn("<h1>Hello &lt;Ann&gt;</h1>", html)
        self.assertIn('<a href="https://example.com/?a=1&amp;b=2">Open</a>', html)

    def test_defaults_and_explicit_bodies_win(self):
        message = MailMessage().to("a@example.com").subject("Hi").text("custom").to_message()

        self.assertEqual(message.get_body(("plain",)).get_content().strip(), "custom")
        self.assertIn("<h1>Hello!</h1>", message.get_body(("html",)).get_content())
        self.assertIn("<p>Regards</p>", message.get_body(("html",)).get_content())


class NotificationTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        for name in ("NOTIFICATIONS_TABLE", "DB_NOTIFICATIONS_CONNECTION"):
            os.environ.pop(name, None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.app = Application(base_path=self.base_path, providers=[(MailProvider, MailConfig), NotificationProvider])
        self.database = InMemoryDatabase()
        self.app.bind("db", self.database)
        migration = load_migration()
        await migration.CreateNotificationsTable("sqlite", Schema(self.database)).up()
        self.user = NotifiedUser({"id": 7, "name": "Ann", "email": "ann@example.com"})

    async def asyncTearDown(self):
        await self.database.engine.dispose()

    async def rows(self):
        return await self.database.sqlite.select("SELECT * FROM notifications")

    def sent(self, mailer=None):
        return Mail.mailer(mailer).transport.messages


class TestNotificationProvider(NotificationTestCase):
    def test_config_defaults_and_binding(self):
        self.assertIsInstance(self.app.make("notification"), ChannelManager)
        self.assertEqual(config("notifications.table"), "notifications")
        self.assertIsNone(config("notifications.connection"))
        self.assertIn("config/notifications.py", self.app.published_resources["notifications"].values())

    async def test_notify_reaches_mail_and_database(self):
        await self.user.notify(InvoicePaid(42))

        [message] = self.sent()
        self.assertEqual(message["To"], "ann@example.com")
        self.assertEqual(message["From"], "App <app@example.com>")
        self.assertEqual(message["Subject"], "Invoice paid")
        self.assertIn("We received 42.", message.get_body(("plain",)).get_content())

        [row] = await self.rows()
        self.assertEqual(row["type"], "InvoicePaid")
        self.assertEqual(row["notifiable_type"], "NotifiedUser")
        self.assertEqual(row["notifiable_id"], "7")
        self.assertEqual(json.loads(row["data"]), {"amount": 42})
        self.assertIsNone(row["read_at"])
        self.assertEqual(len(row["id"]), 32)
        self.assertIsNotNone(row["created_at"])

    async def test_notifications_query_scopes_to_notifiable(self):
        other = NotifiedUser({"id": 8, "name": "Bob", "email": "bob@example.com"})
        await NotificationFacade.send([self.user, other], InvoicePaid(1, ["database"]))
        await self.user.notify(InvoicePaid(2, ["database"]))

        rows = await self.user.notifications()

        self.assertEqual(sorted(json.loads(row["data"])["amount"] for row in rows), [1, 2])
        self.assertEqual(len(await self.rows()), 3)
        self.assertEqual(len({row["id"] for row in await self.rows()}), 3)

    async def test_to_database_wins_over_to_array(self):
        await self.user.notify(DatabaseOnly())

        [row] = await self.rows()
        self.assertEqual(json.loads(row["data"]), {"source": "to_database"})
        self.assertEqual(self.sent(), [])

    async def test_custom_route_and_mailer(self):
        class Routed(NotifiedUser):
            def route_notification_for_mail(self, notification):
                return ("billing@example.com", "Billing")

        notification = InvoicePaid(5, ["mail"])
        notification.mailer = "second"

        await Routed({"id": 1, "name": "Ann"}).notify(notification)

        self.assertEqual(self.sent(), [])
        [message] = self.sent("second")
        self.assertEqual(message["To"], "Billing <billing@example.com>")

    async def test_mailable_with_recipients_is_kept_and_missing_route_skips(self):
        class Explicit(Notification):
            def via(self, notifiable):
                return ["mail"]

            def to_mail(self, notifiable):
                return Mailable().to("fixed@example.com").subject("Fixed")

        await self.user.notify(Explicit())
        await NotifiedUser({"id": 2, "name": "No mail"}).notify(InvoicePaid(1, ["mail"]))

        [message] = self.sent()
        self.assertEqual(message["To"], "fixed@example.com")

    async def test_anonymous_notifiable(self):
        await NotificationFacade.route("mail", "guest@example.com").notify(InvoicePaid(9, ["mail"]))

        [message] = self.sent()
        self.assertEqual(message["To"], "guest@example.com")

    async def test_anonymous_notifiable_cannot_use_database(self):
        with self.assertRaisesRegex(NotificationException, "requires a Notifiable model"):
            await NotificationFacade.route("mail", "guest@example.com").notify(InvoicePaid(9, ["database"]))

    async def test_channel_errors(self):
        class Broken(Notification):
            def via(self, notifiable):
                return ["mail"]

            def to_mail(self, notifiable):
                return "not a mailable"

        with self.assertRaisesRegex(NotificationException, "channel \\[sms\\] is not supported"):
            await self.user.notify(InvoicePaid(1, ["sms"]))
        with self.assertRaisesRegex(NotificationException, "must return a Mailable"):
            await self.user.notify(Broken())
        with self.assertRaisesRegex(NotificationException, "has no to_mail"):
            await self.user.notify(NoMail())

    async def test_extend_adds_a_channel(self):
        delivered = []

        class SmsChannel:
            async def send(self, notifiable, notification):
                delivered.append((notifiable, notification.to_sms(notifiable)))

        class Sms(Notification):
            def via(self, notifiable):
                return ["sms"]

            def to_sms(self, notifiable):
                return f"hi {notifiable.name}"

        NotificationFacade.extend("sms", SmsChannel)
        await self.user.notify(Sms())

        self.assertEqual(delivered, [(self.user, "hi Ann")])


class TestProviderRequirements(IsolatedAsyncioTestCase):
    async def test_missing_mail_and_db_providers_raise(self):
        Application(base_path=Path(tempfile.mkdtemp()), providers=[NotificationProvider])
        user = NotifiedUser({"id": 1, "email": "a@example.com"})

        with self.assertRaisesRegex(RuntimeError, "require MailProvider"):
            await user.notify(InvoicePaid(1, ["mail"]))
        with self.assertRaisesRegex(RuntimeError, "require DatabaseProvider"):
            await user.notify(InvoicePaid(1, ["database"]))

    def test_base_notification_defaults(self):
        notification = Notification()

        self.assertEqual(notification.via(None), [])
        self.assertEqual(notification.to_array(None), {})

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.application import Application
from fastapi_startkit.configuration import config
from fastapi_startkit.facades import Mail
from fastapi_startkit.mail import (
    ArrayMailerConfig,
    ArrayTransport,
    LogTransport,
    Mailable,
    MailManager,
    MailProvider,
    SmtpTransport,
)

ENV = ("MAIL_MAILER", "MAIL_HOST", "MAIL_PORT", "MAIL_ENCRYPTION", "MAIL_FROM_ADDRESS", "MAIL_FROM_NAME")


@dataclass
class ArrayMailConfig:
    default: str = "array"
    from_address: str = "app@example.com"
    from_name: str = "App"
    mailers: dict = field(default_factory=lambda: {"array": ArrayMailerConfig(), "custom": {"driver": "custom"}})


class TestMailProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        for name in ENV:
            os.environ.pop(name, None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def make_app(self, provider=(MailProvider, ArrayMailConfig)):
        return Application(base_path=self.base_path, providers=[provider])

    def test_defaults_without_env(self):
        app = self.make_app(MailProvider)

        self.assertIsInstance(app.make("mail"), MailManager)
        self.assertEqual(config("mail.default"), "log")
        self.assertEqual(config("mail.from_address"), "hello@example.com")
        self.assertEqual(config("mail.mailers.smtp.port"), 587)
        self.assertEqual(config("mail.mailers.smtp.encryption"), "tls")
        self.assertIsInstance(Mail.mailer().transport, LogTransport)
        self.assertIsInstance(Mail.mailer("smtp").transport, SmtpTransport)
        self.assertIsInstance(Mail.mailer("array").transport, ArrayTransport)

    def test_env_overrides_defaults(self):
        os.environ.update({"MAIL_MAILER": "smtp", "MAIL_HOST": "mail.test", "MAIL_PORT": "2525"})

        self.make_app(MailProvider)

        self.assertEqual(config("mail.default"), "smtp")
        self.assertEqual(config("mail.mailers.smtp.host"), "mail.test")
        self.assertEqual(config("mail.mailers.smtp.port"), 2525)

    def test_publishes_config(self):
        app = self.make_app(MailProvider)

        self.assertIn("config/mail.py", app.published_resources["mail"].values())

    async def test_facade_sends_through_default_mailer_with_default_sender(self):
        self.make_app()

        sent = await Mail.send(Mailable().to("a@example.com").subject("Hi").text("body"))

        transport = Mail.mailer().transport
        self.assertEqual(transport.messages, [sent])
        self.assertEqual(sent["From"], "App <app@example.com>")

    async def test_pending_mail_sets_recipients(self):
        self.make_app()

        sent = (
            await Mail.to("a@example.com", name="Ann")
            .cc("b@example.com")
            .bcc("c@example.com")
            .send(Mailable().subject("Hi").text("body"))
        )

        self.assertEqual(sent["To"], "Ann <a@example.com>")
        self.assertEqual(sent["Cc"], "b@example.com")
        self.assertEqual(sent["Bcc"], "c@example.com")

    async def test_extend_registers_a_driver(self):
        self.make_app()
        transport = ArrayTransport()

        Mail.extend("custom", lambda mailer: transport)
        await Mail.mailer("custom").send(Mailable().to("a@example.com").subject("Hi"))

        self.assertEqual(len(transport.messages), 1)
        mailer = Mail.mailer("custom")
        self.assertIs(Mail.mailer("custom"), mailer)
        Mail.forget_mailers()
        self.assertIsNot(Mail.mailer("custom"), mailer)

    def test_unknown_mailer_and_driver(self):
        manager = MailManager({"mailers": {"broken": {"driver": "nope"}}})

        with self.assertRaisesRegex(ValueError, "Mailer \\[missing\\] is not defined"):
            manager.mailer("missing")
        with self.assertRaisesRegex(ValueError, "Mail driver \\[nope\\] is not supported"):
            manager.mailer("broken")
        with self.assertRaises(AttributeError):
            manager._private

    def test_no_default_sender_without_from_address(self):
        self.assertIsNone(MailManager({}).default_sender())

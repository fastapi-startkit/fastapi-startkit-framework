import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest import TestCase

from fastapi_startkit.mail import Address, Mailable


@dataclass
class User:
    email: str
    name: str


class WelcomeMail(Mailable):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self.builds = 0

    def build(self):
        self.builds += 1
        return self.to(self.user).subject(f"Welcome {self.user.name}").text(f"Hi {self.user.name}")


class TestAddress(TestCase):
    def test_formats_with_and_without_name(self):
        self.assertEqual(str(Address("a@example.com")), "a@example.com")
        self.assertEqual(str(Address("a@example.com", "Ann Lee")), "Ann Lee <a@example.com>")

    def test_accepts_strings_tuples_addresses_and_objects(self):
        self.assertEqual(Address.of("a@example.com", "Ann"), Address("a@example.com", "Ann"))
        self.assertEqual(Address.of(("a@example.com", "Ann")), Address("a@example.com", "Ann"))
        self.assertEqual(Address.of(Address("a@example.com")), Address("a@example.com"))
        self.assertEqual(Address.of(User("a@example.com", "Ann")), Address("a@example.com", "Ann"))


class TestMailable(TestCase):
    def test_builds_headers_and_text_body(self):
        message = (
            Mailable()
            .to("a@example.com", name="Ann")
            .cc("b@example.com", "c@example.com")
            .bcc(["d@example.com"])
            .reply_to("support@example.com")
            .from_("app@example.com", "App")
            .subject("Hello")
            .text("Plain body")
            .to_message()
        )

        self.assertEqual(message["To"], "Ann <a@example.com>")
        self.assertEqual(message["Cc"], "b@example.com, c@example.com")
        self.assertEqual(message["Bcc"], "d@example.com")
        self.assertEqual(message["Reply-To"], "support@example.com")
        self.assertEqual(message["From"], "App <app@example.com>")
        self.assertEqual(message["Subject"], "Hello")
        self.assertEqual(message.get_content().strip(), "Plain body")

    def test_html_and_text_become_alternatives(self):
        message = Mailable().to("a@example.com").subject("Hi").text("plain").html("<b>rich</b>").to_message()

        self.assertEqual(message.get_content_type(), "multipart/alternative")
        self.assertEqual(message.get_body(("plain",)).get_content().strip(), "plain")
        self.assertEqual(message.get_body(("html",)).get_content().strip(), "<b>rich</b>")

    def test_html_only_body(self):
        message = Mailable().to("a@example.com").subject("Hi").html("<b>rich</b>").to_message()

        self.assertEqual(message.get_content_type(), "text/html")

    def test_attachments_from_path_and_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.csv"
            path.write_text("a,b\n")
            message = (
                Mailable()
                .to("a@example.com")
                .subject("Report")
                .text("see attached")
                .attach(path)
                .attach_data("raw", "notes.bin")
                .to_message()
            )

        attachments = list(message.iter_attachments())
        self.assertEqual([part.get_filename() for part in attachments], ["report.csv", "notes.bin"])
        self.assertEqual(attachments[0].get_content_type(), "text/csv")
        self.assertEqual(attachments[1].get_content_type(), "application/octet-stream")
        self.assertEqual(attachments[1].get_content(), b"raw")

    def test_default_sender_is_used_when_none_set(self):
        message = Mailable().to("a@example.com").subject("Hi").to_message(Address("app@example.com", "App"))

        self.assertEqual(message["From"], "App <app@example.com>")

    def test_build_hook_runs_once(self):
        mail = WelcomeMail(User("ann@example.com", "Ann"))

        mail.to_message()
        message = mail.to_message()

        self.assertEqual(mail.builds, 1)
        self.assertEqual(message["To"], "Ann <ann@example.com>")
        self.assertEqual(message["Subject"], "Welcome Ann")

    def test_requires_recipients_and_subject(self):
        with self.assertRaisesRegex(ValueError, "no recipients"):
            Mailable().subject("Hi").to_message()
        with self.assertRaisesRegex(ValueError, "no subject"):
            Mailable().to("a@example.com").to_message()

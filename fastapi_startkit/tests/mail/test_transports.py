from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.mail import ArrayTransport, LogTransport, Mailable, SmtpTransport


def message(**parts):
    mailable = Mailable().to("a@example.com").from_("app@example.com").subject("Hello")
    for method, value in parts.items():
        getattr(mailable, method)(value)
    return mailable.to_message()


class TestArrayTransport(IsolatedAsyncioTestCase):
    async def test_keeps_and_flushes_messages(self):
        transport = ArrayTransport()

        await transport.send(message(text="hi"))
        self.assertEqual(len(transport.messages), 1)

        transport.flush()
        self.assertEqual(transport.messages, [])


class TestLogTransport(IsolatedAsyncioTestCase):
    async def test_logs_a_readable_summary(self):
        with self.assertLogs("fastapi_startkit.mail", "INFO") as logs:
            await LogTransport().send(
                Mailable()
                .to("a@example.com")
                .subject("Hello")
                .text("Plain body")
                .html("<b>x</b>")
                .attach_data("x", "a.txt")
                .to_message()
            )

        output = logs.output[0]
        self.assertIn("To: a@example.com", output)
        self.assertIn("Subject: Hello", output)
        self.assertIn("Plain body", output)
        self.assertNotIn("<b>x</b>", output)
        self.assertIn("Attachments: a.txt", output)

    async def test_falls_back_to_html_and_named_channel(self):
        with self.assertLogs("mail.audit", "INFO") as logs:
            await LogTransport("mail.audit").send(message(html="<p>rich</p>"))

        self.assertIn("<p>rich</p>", logs.output[0])


class TestSmtpTransport(IsolatedAsyncioTestCase):
    async def test_starttls_login_and_send(self):
        config = {"host": "smtp.test", "port": 2525, "username": "user", "password": "secret", "encryption": "tls"}
        with mock.patch("smtplib.SMTP") as smtp:
            sent = message(text="hi")
            await SmtpTransport(config).send(sent)

        smtp.assert_called_once_with("smtp.test", 2525, timeout=30.0)
        client = smtp.return_value.__enter__.return_value
        smtp.return_value.starttls.assert_called_once()
        client.login.assert_called_once_with("user", "secret")
        client.send_message.assert_called_once_with(sent)

    async def test_implicit_ssl(self):
        with mock.patch("smtplib.SMTP_SSL") as smtp_ssl:
            await SmtpTransport({"host": "smtp.test", "port": 465, "encryption": "ssl", "timeout": 5}).send(
                message(text="hi")
            )

        args, kwargs = smtp_ssl.call_args
        self.assertEqual(args, ("smtp.test", 465))
        self.assertEqual(kwargs["timeout"], 5.0)
        smtp_ssl.return_value.__enter__.return_value.login.assert_not_called()

    async def test_plain_connection_without_encryption(self):
        with mock.patch("smtplib.SMTP") as smtp:
            await SmtpTransport({"encryption": None}).send(message(text="hi"))

        smtp.assert_called_once_with("127.0.0.1", 587, timeout=30.0)
        smtp.return_value.starttls.assert_not_called()

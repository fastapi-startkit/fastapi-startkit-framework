import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Protocol

SUMMARY_HEADERS = ("From", "To", "Cc", "Bcc", "Reply-To", "Subject")


class Transport(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ArrayTransport:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def flush(self) -> None:
        self.messages.clear()


def summarize(message: EmailMessage) -> str:
    lines = [f"{header}: {message[header]}" for header in SUMMARY_HEADERS if message[header]]
    body = message.get_body(preferencelist=("plain", "html"))
    lines.append("")
    lines.append(body.get_content().rstrip() if body else "")
    attachments = [part.get_filename() for part in message.iter_attachments()]
    if attachments:
        lines.append("")
        lines.append(f"Attachments: {', '.join(name or 'unnamed' for name in attachments)}")
    return "\n".join(lines)


class LogTransport:
    def __init__(self, channel: str | None = None) -> None:
        self.logger = logging.getLogger(channel or "fastapi_startkit.mail")

    async def send(self, message: EmailMessage) -> None:
        self.logger.info("Mail sent\n%s", summarize(message))


class SmtpTransport:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self.deliver, message)

    def connect(self) -> smtplib.SMTP:
        host = self.config.get("host") or "127.0.0.1"
        port = int(self.config.get("port") or 587)
        timeout = float(self.config.get("timeout") or 30)
        if self.config.get("encryption") == "ssl":
            return smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
        client = smtplib.SMTP(host, port, timeout=timeout)
        if self.config.get("encryption") == "tls":
            client.starttls(context=ssl.create_default_context())
        return client

    def deliver(self, message: EmailMessage) -> None:
        with self.connect() as client:
            if self.config.get("username"):
                client.login(self.config["username"], self.config.get("password") or "")
            client.send_message(message)

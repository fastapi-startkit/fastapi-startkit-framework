from email.message import EmailMessage
from typing import Any

from fastapi_startkit.mail import Mailable, Mailer, PendingMail
from fastapi_startkit.mail.manager import MailManager, TransportFactory

class Mail:
    @staticmethod
    def mailer(name: str | None = None) -> Mailer: ...
    @staticmethod
    async def send(mailable: Mailable) -> EmailMessage: ...
    @staticmethod
    def to(*values: Any, name: str | None = None) -> PendingMail: ...
    @staticmethod
    def extend(driver: str, factory: TransportFactory) -> MailManager: ...
    @staticmethod
    def forget_mailers() -> MailManager: ...

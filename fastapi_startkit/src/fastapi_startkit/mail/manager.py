from collections.abc import Callable
from email.message import EmailMessage
from typing import Any, Self

from .mailable import Address, AddressLike, Mailable
from .transports import ArrayTransport, LogTransport, SmtpTransport, Transport

TransportFactory = Callable[[dict[str, Any]], Transport]


class Mailer:
    def __init__(self, name: str, transport: Transport, sender: Address | None = None):
        self.name = name
        self.transport = transport
        self.sender = sender

    async def send(self, mailable: Mailable) -> EmailMessage:
        message = mailable.to_message(self.sender)
        await self.transport.send(message)
        return message

    def to(self, *values: AddressLike, name: str | None = None) -> "PendingMail":
        return PendingMail(self).to(*values, name=name)


class PendingMail:
    def __init__(self, mailer: Mailer):
        self.mailer = mailer
        self.recipients: dict[str, list[tuple[tuple[AddressLike, ...], str | None]]] = {"to": [], "cc": [], "bcc": []}

    def to(self, *values: AddressLike, name: str | None = None) -> Self:
        self.recipients["to"].append((values, name))
        return self

    def cc(self, *values: AddressLike, name: str | None = None) -> Self:
        self.recipients["cc"].append((values, name))
        return self

    def bcc(self, *values: AddressLike, name: str | None = None) -> Self:
        self.recipients["bcc"].append((values, name))
        return self

    async def send(self, mailable: Mailable) -> EmailMessage:
        for method, entries in self.recipients.items():
            for values, name in entries:
                getattr(mailable, method)(*values, name=name)
        return await self.mailer.send(mailable)


class MailManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._mailers: dict[str, Mailer] = {}
        self._creators: dict[str, TransportFactory] = {
            "smtp": SmtpTransport,
            "log": lambda mailer: LogTransport(mailer.get("channel")),
            "array": lambda mailer: ArrayTransport(),
        }

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)
        return getattr(self.mailer(), method)

    def mailer(self, name: str | None = None) -> Mailer:
        resolved: str = name or self.config.get("default") or "log"
        if resolved not in self._mailers:
            self._mailers[resolved] = self.resolve(resolved)
        return self._mailers[resolved]

    def resolve(self, name: str) -> Mailer:
        config = self.config.get("mailers", {}).get(name)
        if config is None:
            raise ValueError(f"Mailer [{name}] is not defined.")

        driver = config.get("driver")
        if driver not in self._creators:
            raise ValueError(f"Mail driver [{driver}] is not supported.")
        return Mailer(name, self._creators[driver](config), self.default_sender())

    def default_sender(self) -> Address | None:
        address = self.config.get("from_address")
        return Address(address, self.config.get("from_name") or None) if address else None

    def extend(self, driver: str, factory: TransportFactory) -> Self:
        self._creators[driver] = factory
        return self

    def forget_mailers(self) -> Self:
        self._mailers.clear()
        return self

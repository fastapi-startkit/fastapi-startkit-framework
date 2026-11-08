import mimetypes
from dataclasses import dataclass
from email.headerregistry import Address as HeaderAddress
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Self

AddressLike = Any


@dataclass(frozen=True)
class Address:
    email: str
    name: str | None = None

    def __str__(self) -> str:
        return str(HeaderAddress(display_name=self.name or "", addr_spec=self.email))

    @classmethod
    def of(cls, value: AddressLike, name: str | None = None) -> "Address":
        if isinstance(value, Address):
            return value
        if isinstance(value, tuple):
            return cls(*value)
        if isinstance(value, str):
            return cls(value, name)
        return cls(value.email, name or getattr(value, "name", None))


@dataclass(frozen=True)
class Attachment:
    data: bytes
    name: str
    mime: str

    @classmethod
    def from_path(cls, path: str | Path, name: str | None = None, mime: str | None = None) -> "Attachment":
        file = Path(path)
        return cls(file.read_bytes(), name or file.name, mime or guess_mime(file.name))


def guess_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def addresses(values: tuple[AddressLike, ...], name: str | None) -> list[Address]:
    if len(values) == 1 and isinstance(values[0], list):
        values = tuple(values[0])
    return [Address.of(value, name if len(values) == 1 else None) for value in values]


class Mailable:
    def __init__(self) -> None:
        self._to: list[Address] = []
        self._cc: list[Address] = []
        self._bcc: list[Address] = []
        self._reply_to: list[Address] = []
        self._from: Address | None = None
        self._subject: str | None = None
        self._html: str | None = None
        self._text: str | None = None
        self._attachments: list[Attachment] = []
        self._built = False

    def build(self) -> Any:
        return self

    def to(self, *values: AddressLike, name: str | None = None) -> Self:
        self._to.extend(addresses(values, name))
        return self

    def cc(self, *values: AddressLike, name: str | None = None) -> Self:
        self._cc.extend(addresses(values, name))
        return self

    def bcc(self, *values: AddressLike, name: str | None = None) -> Self:
        self._bcc.extend(addresses(values, name))
        return self

    def reply_to(self, *values: AddressLike, name: str | None = None) -> Self:
        self._reply_to.extend(addresses(values, name))
        return self

    def from_(self, value: AddressLike, name: str | None = None) -> Self:
        self._from = Address.of(value, name)
        return self

    def subject(self, subject: str) -> Self:
        self._subject = subject
        return self

    def html(self, html: str) -> Self:
        self._html = html
        return self

    def text(self, text: str) -> Self:
        self._text = text
        return self

    def attach(self, path: str | Path, name: str | None = None, mime: str | None = None) -> Self:
        self._attachments.append(Attachment.from_path(path, name, mime))
        return self

    def attach_data(self, data: bytes | str, name: str, mime: str | None = None) -> Self:
        content = data.encode() if isinstance(data, str) else data
        self._attachments.append(Attachment(content, name, mime or guess_mime(name)))
        return self

    def has_to(self) -> bool:
        return bool(self._to)

    def prepare(self) -> Self:
        if not self._built:
            self._built = True
            self.build()
        return self

    def to_message(self, default_from: Address | None = None) -> EmailMessage:
        self.prepare()
        sender = self._from or default_from
        if not self._to and not self._cc and not self._bcc:
            raise ValueError(f"Mailable [{type(self).__name__}] has no recipients.")
        if not self._subject:
            raise ValueError(f"Mailable [{type(self).__name__}] has no subject.")

        message = EmailMessage()
        message["Subject"] = self._subject
        if sender:
            message["From"] = str(sender)
        for header, values in (("To", self._to), ("Cc", self._cc), ("Bcc", self._bcc), ("Reply-To", self._reply_to)):
            if values:
                message[header] = ", ".join(str(value) for value in values)

        message.set_content(self._text if self._text is not None else "")
        if self._html is not None:
            if self._text is None:
                message.set_content(self._html, subtype="html")
            else:
                message.add_alternative(self._html, subtype="html")
        for attachment in self._attachments:
            maintype, subtype = attachment.mime.split("/", 1)
            message.add_attachment(attachment.data, maintype=maintype, subtype=subtype, filename=attachment.name)
        return message

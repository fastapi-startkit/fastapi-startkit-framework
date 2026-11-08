from html import escape
from typing import Self

from fastapi_startkit.mail import Mailable


class MailMessage(Mailable):
    def __init__(self) -> None:
        super().__init__()
        self._greeting: str | None = None
        self._lines: list[str] = []
        self._action: tuple[str, str] | None = None
        self._salutation: str | None = None

    def greeting(self, greeting: str) -> Self:
        self._greeting = greeting
        return self

    def line(self, line: str) -> Self:
        self._lines.append(line)
        return self

    def action(self, text: str, url: str) -> Self:
        self._action = (text, url)
        return self

    def salutation(self, salutation: str) -> Self:
        self._salutation = salutation
        return self

    def build(self) -> Self:
        if self._text is None:
            self.text(self.render_text())
        if self._html is None:
            self.html(self.render_html())
        return self

    def render_text(self) -> str:
        parts = [self._greeting or "Hello!", *self._lines]
        if self._action:
            parts.append(f"{self._action[0]}: {self._action[1]}")
        parts.append(self._salutation or "Regards")
        return "\n\n".join(parts)

    def render_html(self) -> str:
        parts = [f"<h1>{escape(self._greeting or 'Hello!')}</h1>"]
        parts.extend(f"<p>{escape(line)}</p>" for line in self._lines)
        if self._action:
            text, url = self._action
            parts.append(f'<p><a href="{escape(url, quote=True)}">{escape(text)}</a></p>')
        parts.append(f"<p>{escape(self._salutation or 'Regards')}</p>")
        return "\n".join(parts)
